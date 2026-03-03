from fastapi import APIRouter, UploadFile, File, Depends, HTTPException, Form
from sqlalchemy.orm import Session
from datetime import date
from uuid import uuid4
import os
import pandas as pd
from fastapi.responses import FileResponse

from app.database import SessionLocal
from app.models.mostvaluedcharts import (
    MostValCompanyChart,
    MostValCompanyChartUpload,
    MostValHouseChart,
    MostValHouseChartUpload
)

router = APIRouter(prefix="/mostvaluedcharts", tags=["Most Valued Charts"])

UPLOAD_BASE = "uploads/mostvaluedcharts"
os.makedirs(UPLOAD_BASE, exist_ok=True)


# ============================================================
# DB Session
# ============================================================
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# ============================================================
# Helper: Get Models by Category
# ============================================================
def get_models(category: str):
    if category == "company":
        return (
            MostValCompanyChart,
            MostValCompanyChartUpload,
            ["COMPANY", "ISIN", "VAL", "TRN_DATE"]  # first column ignored
        )
    elif category == "house":
        return (
            MostValHouseChart,
            MostValHouseChartUpload,
            ["H_ID", "HOUSE_NAME", "VALUE", "TRN_DATE"]  # first column ignored
        )
    else:
        raise HTTPException(400, "Invalid category. Use 'company' or 'house'.")


# ============================================================
# Helper: Read File (ignore first column)
# ============================================================
def read_file_without_headers(file_path: str, required_columns: list, category: str):
    # Read CSV or Excel
    if file_path.endswith(".csv"):
        df = pd.read_csv(file_path, header=None)
    else:
        df = pd.read_excel(file_path, header=None)

    # Remove fully empty columns
    df = df.dropna(axis=1, how="all")

    # Ignore the first column
    df = df.iloc[:, 1:1 + len(required_columns)]

    # Check column count
    if df.shape[1] < len(required_columns):
        raise HTTPException(
            status_code=400,
            detail=f"{category} file must contain at least {len(required_columns)+1} columns (first ignored)"
        )

    # Assign proper column names
    df.columns = required_columns

    # Convert date column
    df["TRN_DATE"] = pd.to_datetime(df["TRN_DATE"]).dt.date

    return df


# ============================================================
# Upload
# ============================================================
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

    # Save file
    category_folder = os.path.join(UPLOAD_BASE, category)
    os.makedirs(category_folder, exist_ok=True)
    filename = f"{date.today()}_{uuid4()}_{file.filename}"
    file_path = os.path.join(category_folder, filename)
    with open(file_path, "wb") as f:
        f.write(await file.read())

    # Read file ignoring first column
    df = read_file_without_headers(file_path, required_columns, category)

    # Insert records
    records = [
        DataModel(**{col: row[col] for col in required_columns}, group_id=group_id)
        for _, row in df.iterrows()
    ]

    upload_row = UploadModel(
        group_id=group_id,
        upload_date=upload_date,
        data_date=data_date,
        data_type=category,
        file_name=filename,
        file_path=file_path
    )

    db.add(upload_row)
    db.bulk_save_objects(records)
    db.commit()

    return {
        "message": f"{category} file uploaded successfully",
        "group_id": group_id
    }

# ============================================================
# Get all uploads across all categories
# ============================================================
@router.get("/uploads/all")
def get_all_uploads(db: Session = Depends(get_db)):
    all_uploads = []

    # List of categories
    categories = ["company", "house"]

    for category in categories:
        _, UploadModel, _ = get_models(category)
        uploads = db.query(UploadModel).order_by(UploadModel.upload_date.desc()).all()
        
        # Add category info to each upload
        for u in uploads:
            all_uploads.append({
                "group_id": u.group_id,
                "file_name": u.file_name,
                "upload_date": u.upload_date,
                "data_date": u.data_date,
                "category": category
            })

    return all_uploads

# ============================================================
# Get Latest Data
# ============================================================
@router.get("/{category}/latest")
def get_latest(category: str, db: Session = Depends(get_db)):
    DataModel, UploadModel, _ = get_models(category)
    latest_upload = db.query(UploadModel).order_by(
        UploadModel.data_date.desc()
    ).first()

    if not latest_upload:
        raise HTTPException(404, "No upload found")

    data = db.query(DataModel).filter(
        DataModel.group_id == latest_upload.group_id
    ).all()

    return {
        "data_date": latest_upload.data_date,
        "records": data
    }


# ============================================================
# Download
# ============================================================
@router.get("/{category}/download/{group_id}")
def download_file(category: str, group_id: str, db: Session = Depends(get_db)):
    _, UploadModel, _ = get_models(category)
    upload = db.query(UploadModel).filter(
        UploadModel.group_id == group_id
    ).first()

    if not upload or not os.path.exists(upload.file_path):
        raise HTTPException(404, "File not found")

    return FileResponse(upload.file_path, filename=upload.file_name)


# ============================================================
# Update Upload
# ============================================================
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
    upload = db.query(UploadModel).filter(
        UploadModel.group_id == group_id
    ).first()

    if not upload:
        raise HTTPException(404, "Upload not found")

    if upload_date:
        upload.upload_date = upload_date
    if data_date:
        upload.data_date = data_date

    if file:
        if upload.file_path and os.path.exists(upload.file_path):
            os.remove(upload.file_path)

        category_folder = os.path.join(UPLOAD_BASE, category)
        os.makedirs(category_folder, exist_ok=True)
        filename = f"{date.today()}_{uuid4()}_{file.filename}"
        file_path = os.path.join(category_folder, filename)
        with open(file_path, "wb") as f:
            f.write(await file.read())

        upload.file_name = filename
        upload.file_path = file_path

        # Delete old records
        db.query(DataModel).filter(DataModel.group_id == group_id).delete(synchronize_session=False)

        # Read new file ignoring first column
        df = read_file_without_headers(file_path, required_columns, category)
        new_records = [
            DataModel(**{col: row[col] for col in required_columns}, group_id=group_id)
            for _, row in df.iterrows()
        ]
        db.bulk_save_objects(new_records)

    db.commit()
    return {
        "message": f"{category} upload updated successfully",
        "group_id": group_id
    }


# ============================================================
# Delete
# ============================================================
@router.delete("/{category}/upload/{group_id}")
def delete_upload(category: str, group_id: str, db: Session = Depends(get_db)):
    DataModel, UploadModel, _ = get_models(category)
    upload = db.query(UploadModel).filter(
        UploadModel.group_id == group_id
    ).first()

    if not upload:
        raise HTTPException(404, "Upload not found")

    # Delete records
    db.query(DataModel).filter(DataModel.group_id == group_id).delete()
    # Delete file
    if upload.file_path and os.path.exists(upload.file_path):
        os.remove(upload.file_path)
    db.delete(upload)
    db.commit()

    return {"message": f"{category} upload deleted successfully"}