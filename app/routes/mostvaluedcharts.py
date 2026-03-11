import io
from datetime import date
from typing import List, Dict, Any
from uuid import uuid4

import pandas as pd
from fastapi import APIRouter, Depends, UploadFile, File, Form, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from sqlalchemy import desc

from app.database import SessionLocal
from app.models.mostvaluedcharts import (
    MostValCompanyChart,
    MostValCompanyChartUpload,
    MostValHouseChart,
    MostValHouseChartUpload
)
from app.s3_utils import (
    upload_file_to_s3,
    delete_file_from_s3,
    get_file_stream_from_s3,
    get_s3_file_url
)

router = APIRouter(prefix="/mostvaluedcharts", tags=["Most Valued Charts"])

# -------------------- DB DEPENDENCY --------------------
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# -------------------- Helpers --------------------
def get_models(category: str):
    if category == "company":
        return MostValCompanyChart, MostValCompanyChartUpload, ["COMPANY", "ISIN", "VAL", "TRN_DATE"]
    elif category == "house":
        return MostValHouseChart, MostValHouseChartUpload, ["H_ID", "HOUSE_NAME", "VALUE", "TRN_DATE"]
    else:
        raise HTTPException(400, "Invalid category. Use 'company' or 'house'.")

def read_file_from_bytes(file_bytes: bytes, required_columns: list, category: str):
    # Read Excel first, fallback to CSV
    try:
        df = pd.read_excel(io.BytesIO(file_bytes), header=None)
    except Exception:
        try:
            df = pd.read_csv(io.StringIO(file_bytes.decode("utf-8")), header=None)
        except Exception:
            raise HTTPException(400, f"Failed to read {category} file as CSV or Excel.")

    df = df.dropna(axis=1, how="all")  # remove empty columns
    df = df.iloc[:, 1:1+len(required_columns)]  # ignore first column

    if df.shape[1] != len(required_columns):
        raise HTTPException(
            400,
            detail=f"{category} file must have exactly {len(required_columns)+1} columns (first ignored)"
        )

    df.columns = required_columns
    df["TRN_DATE"] = pd.to_datetime(df["TRN_DATE"]).dt.date
    return df

# -------------------- UPLOAD --------------------
@router.post("/{category}/upload")
async def upload_file(
    category: str,
    upload_date: date = Form(...),
    data_date: date = Form(...),
    file: UploadFile = File(...),
    db: Session = Depends(get_db)
):
    DataModel, UploadModel, required_columns = get_models(category)
    group_id = str(uuid4())
    file_bytes = await file.read()
    
    # Upload file to S3
    s3_key = upload_file_to_s3(io.BytesIO(file_bytes), f"{category}/{uuid4()}_{file.filename}")

    # Read file into DataFrame
    df = read_file_from_bytes(file_bytes, required_columns, category)

    # Insert DB records
    records = [DataModel(**{col: row[col] for col in required_columns}, group_id=group_id) for _, row in df.iterrows()]
    upload_row = UploadModel(
        group_id=group_id,
        upload_date=upload_date,
        data_date=data_date,
        data_type=category,
        file_name=file.filename,
        file_path=s3_key
    )

    db.add(upload_row)
    db.bulk_save_objects(records)
    db.commit()

    return {
        "message": f"{category} file uploaded successfully",
        "group_id": group_id,
        "file_s3_url": get_s3_file_url(s3_key)
    }

# -------------------- LIST ALL UPLOADS --------------------
@router.get("/uploads/all")
def get_all_uploads(db: Session = Depends(get_db)):
    all_uploads = []
    for category in ["company", "house"]:
        _, UploadModel, _ = get_models(category)
        uploads = db.query(UploadModel).order_by(UploadModel.upload_date.desc()).all()
        for u in uploads:
            all_uploads.append({
                "group_id": u.group_id,
                "file_name": u.file_name,
                "upload_date": u.upload_date,
                "data_date": u.data_date,
                "category": category,
                "file_s3_url": get_s3_file_url(u.file_path)
            })
    return all_uploads

# -------------------- GET LATEST --------------------
@router.get("/{category}/latest")
def get_latest(category: str, db: Session = Depends(get_db)):
    DataModel, UploadModel, _ = get_models(category)
    latest_upload = db.query(UploadModel).order_by(UploadModel.data_date.desc()).first()
    if not latest_upload:
        raise HTTPException(404, "No upload found")
    data = db.query(DataModel).filter(DataModel.group_id == latest_upload.group_id).all()
    return {
        "data_date": latest_upload.data_date,
        "records": data
    }

# -------------------- DOWNLOAD --------------------
@router.get("/{category}/download/{group_id}")
def download_file(category: str, group_id: str, db: Session = Depends(get_db)):
    _, UploadModel, _ = get_models(category)
    upload = db.query(UploadModel).filter(UploadModel.group_id == group_id).first()
    if not upload:
        raise HTTPException(404, "Upload not found")
    file_stream = get_file_stream_from_s3(upload.file_path)
    return StreamingResponse(
        file_stream,
        media_type="application/octet-stream",
        headers={"Content-Disposition": f'attachment; filename="{upload.file_name}"'}
    )

# -------------------- UPDATE --------------------
@router.put("/{category}/upload/{group_id}")
async def update_upload(
    category: str,
    group_id: str,
    upload_date: date = Form(None),
    data_date: date = Form(None),
    file: UploadFile = File(None),
    db: Session = Depends(get_db)
):
    DataModel, UploadModel, required_columns = get_models(category)
    upload = db.query(UploadModel).filter(UploadModel.group_id == group_id).first()
    if not upload:
        raise HTTPException(404, "Upload not found")

    if upload_date:
        upload.upload_date = upload_date
    if data_date:
        upload.data_date = data_date

    new_records = []

    if file:
        # Delete old S3 file
        delete_file_from_s3(upload.file_path)
        # Upload new file to S3
        file_bytes = await file.read()
        s3_key = upload_file_to_s3(io.BytesIO(file_bytes), f"{category}/{uuid4()}_{file.filename}")
        upload.file_name = file.filename
        upload.file_path = s3_key

        # Delete old DB records
        db.query(DataModel).filter(DataModel.group_id == group_id).delete(synchronize_session=False)

        # Insert new records
        df = read_file_from_bytes(file_bytes, required_columns, category)
        new_records = [DataModel(**{col: row[col] for col in required_columns}, group_id=group_id) for _, row in df.iterrows()]
        db.bulk_save_objects(new_records)

    db.commit()
    db.refresh(upload)

    return {
        "message": f"{category} upload updated successfully",
        "group_id": group_id,
        "file_s3_url": get_s3_file_url(upload.file_path),
        "records_inserted": len(new_records)
    }

# -------------------- DELETE --------------------
@router.delete("/{category}/upload/{group_id}")
def delete_upload(category: str, group_id: str, db: Session = Depends(get_db)):
    DataModel, UploadModel, _ = get_models(category)
    upload = db.query(UploadModel).filter(UploadModel.group_id == group_id).first()
    if not upload:
        raise HTTPException(404, "Upload not found")

    # Delete DB records
    db.query(DataModel).filter(DataModel.group_id == group_id).delete()
    # Delete S3 file
    delete_file_from_s3(upload.file_path)

    db.delete(upload)
    db.commit()

    return {"message": f"{category} upload deleted successfully"}