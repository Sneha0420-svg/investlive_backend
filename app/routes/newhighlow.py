import io
from datetime import date
from typing import List, Dict, Any
from uuid import uuid4
import math
import pandas as pd
from fastapi import APIRouter, UploadFile, File, Depends, HTTPException, Form
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.models.newhighlow import (
    FiftyTwoWeekHighLow,
    FiftyTwoWeekHighLowUpload,
    MultiYearHighLow,
    MultiYearHighLowUpload,
    CircuitUpLow,
    CircuitUpLowUpload
)
from app.s3_utils import (
    upload_file_to_s3,
    delete_file_from_s3,
    get_file_stream_from_s3,
    get_s3_file_url
)

router = APIRouter(prefix="/NewHighLow", tags=["New High / Low"])

# -------------------- DB DEPENDENCY --------------------
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# -------------------- Helpers --------------------
def clean_nan(val):
    return None if isinstance(val, float) and math.isnan(val) else val

def get_models(category: str):
    if category == "52-week":
        return FiftyTwoWeekHighLow, FiftyTwoWeekHighLowUpload, 7, [
            "COMPANY", "ISIN", "CMP", "52WKH", "52WKL", "CH_RS", "CH_PER"
        ]
    elif category == "circuit":
        return CircuitUpLow, CircuitUpLowUpload, 11, [
            "COMPANY", "ISIN", "CMP", "CH_PER", "VOL", "VALUE", "TRADE",
            "52WKH", "52WKHDT", "52WKL", "52WKLDT"
        ]
    elif category == "multi-year":
        return MultiYearHighLow, MultiYearHighLowUpload, 11, [
            "COMPANY", "ISIN", "MCAP", "CMP",
            "MYRH", "MYRH_DT", "MYRL", "MYRL_DT",
            "SINCE", "TYPE", "ID"
        ]
    else:
        raise HTTPException(400, "Invalid category")

def read_file_bytes(file_bytes: bytes, expected_cols: int, columns: list, category: str):
    try:
        df = pd.read_excel(io.BytesIO(file_bytes), header=None)
    except Exception:
        try:
            df = pd.read_csv(io.StringIO(file_bytes.decode("utf-8")), header=None)
        except Exception:
            raise HTTPException(400, f"Failed to read {category} file as CSV or Excel")
    if df.shape[1] != expected_cols:
        raise HTTPException(400, f"{category} file must have exactly {expected_cols} columns")
    df.columns = columns
    return df

def generate_s3_key(category: str, filename: str):
    return f"newhighlow/{category}/{uuid4()}_{filename}"

# -------------------- UPLOAD --------------------
@router.post("/upload/{category}")
async def upload_new_high_low(
    category: str,
    upload_date: date = Form(...),
    data_date: date = Form(...),
    file: UploadFile = File(...),
    db: Session = Depends(get_db)
):
    DataModel, UploadModel, expected_cols, columns = get_models(category)
    group_id = str(uuid4())
    file_bytes = await file.read()

    # Upload to S3
    s3_key = upload_file_to_s3(io.BytesIO(file_bytes), generate_s3_key(category, file.filename))

    # Read file
    df = read_file_bytes(file_bytes, expected_cols, columns, category)

    # Store upload info
    upload_row = UploadModel(
        group_id=group_id,
        upload_date=upload_date,
        data_date=data_date,
        category=category,
        file_name=file.filename,
        file_path=s3_key
    )
    db.add(upload_row)

    # Insert data only if latest
    latest_upload = db.query(UploadModel).order_by(UploadModel.data_date.desc()).first()
    if not latest_upload or data_date >= latest_upload.data_date:
        db.query(DataModel).delete(synchronize_session=False)
        records = []
        for _, row in df.iterrows():
            if category == "52-week":
                records.append(DataModel(
                    COMPANY=clean_nan(row["COMPANY"]),
                    ISIN=row["ISIN"],
                    CMP=clean_nan(row["CMP"]),
                    WKH_52=clean_nan(row["52WKH"]),
                    WKL_52=clean_nan(row["52WKL"]),
                    CH_RS=clean_nan(row["CH_RS"]),
                    CH_PER=clean_nan(row["CH_PER"]),
                    group_id=group_id
                ))
            elif category == "circuit":
                records.append(DataModel(
                    COMPANY=clean_nan(row["COMPANY"]),
                    ISIN=row["ISIN"],
                    CMP=clean_nan(row["CMP"]),
                    CH_PER=clean_nan(row["CH_PER"]),
                    VOL=row["VOL"],
                    VALUE=row["VALUE"],
                    TRADE=row["TRADE"],
                    WKH_52=clean_nan(row["52WKH"]),
                    WKH_DT_52=str(row["52WKHDT"]),
                    WKL_52=clean_nan(row["52WKL"]),
                    WKL_DT_52=str(row["52WKLDT"]),
                    group_id=group_id
                ))
            else:  # multi-year
                records.append(DataModel(
                    COMPANY=clean_nan(row["COMPANY"]),
                    ISIN=row["ISIN"],
                    MCAP=clean_nan(row["MCAP"]),
                    CMP=clean_nan(row["CMP"]),
                    MYRH=clean_nan(row["MYRH"]),
                    MYRH_DT=str(row["MYRH_DT"]),
                    MYRL=clean_nan(row["MYRL"]),
                    MYRL_DT=str(row["MYRL_DT"]),
                    SINCE=str(row["SINCE"]),
                    TYPE=int(row["TYPE"]),
                    ID=int(row["ID"]),
                    group_id=group_id
                ))
        db.bulk_save_objects(records)

    db.commit()
    return {
        "message": f"{category} data uploaded successfully",
        "group_id": group_id,
        "records": len(df),
        "file_s3_url": get_s3_file_url(s3_key)
    }

# -------------------- LIST UPLOADS --------------------
@router.get("/uploads/{category}")
def get_new_high_low_uploads(category: str, db: Session = Depends(get_db)):
    _, UploadModel, _, _ = get_models(category)
    uploads = db.query(UploadModel).order_by(UploadModel.upload_date.desc()).all()
    return [
        {
            "id": u.id,
            
            "group_id": u.group_id,
            "upload_date": u.upload_date,
            "data_date": u.data_date,
            "file_name": u.file_name,
            "category":u.category,
            "file_s3_url": get_s3_file_url(u.file_path)
        } for u in uploads
    ]

# -------------------- LATEST DATA --------------------
@router.get("/latest/{category}")
def get_latest_data_new_high_low(category: str, db: Session = Depends(get_db)):
    DataModel, UploadModel, _, _ = get_models(category)
    latest_upload = db.query(UploadModel).order_by(UploadModel.data_date.desc()).first()
    if not latest_upload:
        return {"message": "No uploads found", "records": []}

    data_rows = db.query(DataModel).filter(DataModel.group_id == latest_upload.group_id).all()
    result = [row.__dict__ for row in data_rows]
    for r in result:
        r.pop("_sa_instance_state", None)
    return {"latest_data_date": latest_upload.data_date, "records": result, "count": len(result)}

# -------------------- DOWNLOAD --------------------
@router.get("/download/{category}/{group_id}")
def download_new_high_low_file(category: str, group_id: str, db: Session = Depends(get_db)):
    _, UploadModel, _, _ = get_models(category)
    upload = db.query(UploadModel).filter(UploadModel.group_id == group_id).first()
    if not upload:
        raise HTTPException(404, "Upload not found")

    file_stream = get_file_stream_from_s3(upload.file_path)
    return StreamingResponse(file_stream, media_type="application/octet-stream",
                             headers={"Content-Disposition": f'attachment; filename="{upload.file_name}"'})

# -------------------- UPDATE --------------------
@router.put("/upload/{category}/{group_id}")
async def update_new_high_low_upload(
    category: str,
    group_id: str,
    upload_date: date = Form(None),
    data_date: date = Form(None),
    file: UploadFile = File(None),
    db: Session = Depends(get_db)
):
    DataModel, UploadModel, expected_cols, columns = get_models(category)
    upload = db.query(UploadModel).filter(UploadModel.group_id == group_id).first()
    if not upload:
        raise HTTPException(404, "Upload not found")

    if upload_date:
        upload.upload_date = upload_date
    if data_date:
        upload.data_date = data_date

    new_records = []
    if file:
        # delete old S3 file
        if upload.file_path:
            delete_file_from_s3(upload.file_path)

        # upload new file
        file_bytes = await file.read()
        s3_key = upload_file_to_s3(io.BytesIO(file_bytes), generate_s3_key(category, file.filename))
        upload.file_name = file.filename
        upload.file_path = s3_key

        # delete old data
        db.query(DataModel).filter(DataModel.group_id == group_id).delete(synchronize_session=False)

        # read new data
        df = read_file_bytes(file_bytes, expected_cols, columns, category)

        for _, row in df.iterrows():
            if category == "52-week":
                new_records.append(DataModel(
                    COMPANY=clean_nan(row["COMPANY"]),
                    ISIN=row["ISIN"],
                    CMP=clean_nan(row["CMP"]),
                    WKH_52=clean_nan(row["52WKH"]),
                    WKL_52=clean_nan(row["52WKL"]),
                    CH_RS=clean_nan(row["CH_RS"]),
                    CH_PER=clean_nan(row["CH_PER"]),
                    group_id=group_id
                ))
            elif category == "circuit":
                new_records.append(DataModel(
                    COMPANY=clean_nan(row["COMPANY"]),
                    ISIN=row["ISIN"],
                    CMP=clean_nan(row["CMP"]),
                    CH_PER=clean_nan(row["CH_PER"]),
                    VOL=row["VOL"],
                    VALUE=row["VALUE"],
                    TRADE=row["TRADE"],
                    WKH_52=clean_nan(row["52WKH"]),
                    WKH_DT_52=str(row["52WKHDT"]),
                    WKL_52=clean_nan(row["52WKL"]),
                    WKL_DT_52=str(row["52WKLDT"]),
                    group_id=group_id
                ))
            else:
                new_records.append(DataModel(
                    COMPANY=clean_nan(row["COMPANY"]),
                    ISIN=row["ISIN"],
                    MCAP=clean_nan(row["MCAP"]),
                    CMP=clean_nan(row["CMP"]),
                    MYRH=clean_nan(row["MYRH"]),
                    MYRH_DT=str(row["MYRH_DT"]),
                    MYRL=clean_nan(row["MYRL"]),
                    MYRL_DT=str(row["MYRL_DT"]),
                    SINCE=str(row["SINCE"]),
                    TYPE=int(row["TYPE"]),
                    ID=int(row["ID"]),
                    group_id=group_id
                ))
        if new_records:
            db.bulk_save_objects(new_records)

    db.commit()
    return {"message": "Upload updated successfully", "group_id": group_id}

# -------------------- DELETE --------------------
@router.delete("/upload/{category}/{group_id}")
def delete_new_high_low_upload(category: str, group_id: str, db: Session = Depends(get_db)):
    DataModel, UploadModel, _, _ = get_models(category)
    upload = db.query(UploadModel).filter(UploadModel.group_id == group_id).first()
    if not upload:
        raise HTTPException(404, "Upload not found")

    # delete data
    db.query(DataModel).filter(DataModel.group_id == group_id).delete(synchronize_session=False)

    # delete S3 file
    if upload.file_path:
        delete_file_from_s3(upload.file_path)

    db.delete(upload)
    db.commit()
    return {"message": "Upload deleted successfully"}