import os
import io
from datetime import date
from typing import List, Dict, Any
from uuid import uuid4

import pandas as pd
from fastapi import (
    APIRouter,
    Depends,
    UploadFile,
    File,
    HTTPException,
    Form
)
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from sqlalchemy import desc

from app.database import SessionLocal
from app.models.instocktrend import InstockTrendData, Indstocktrendupload

UPLOAD_FOLDER = "uploads/indstocktrend"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

router = APIRouter(
    prefix="/indstocktrend",
    tags=["InstockTrend"]
)


# -------------------- DB DEPENDENCY --------------------
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# -------------------- UPLOAD EXCEL --------------------
@router.post("/upload")
async def upload_multiple_data(
    files: List[UploadFile] = File(...),
    upload_date: date = Form(...),
    data_date: date = Form(...),
    data_type: str = Form(...),
    db: Session = Depends(get_db)
):
    all_records = []
    upload_ids = []

    for file in files:
        filename = f"{date.today()}_{uuid4()}_{file.filename}"
        file_path = os.path.join(UPLOAD_FOLDER, filename)

        # Save file
        with open(file_path, "wb") as f:
            f.write(await file.read())

        # Save upload metadata
        upload_record = Indstocktrendupload(
            upload_date=upload_date,
            data_date=data_date,
            data_type=data_type,
            file_name=filename,
            file_path=file_path
        )
        db.add(upload_record)
        db.commit()
        db.refresh(upload_record)
        upload_ids.append(upload_record.id)

        # Read Excel / CSV (NO HEADER)
        try:
            if filename.endswith((".xlsx", ".xls")):
                df = pd.read_excel(file_path, header=None)
            elif filename.endswith(".csv"):
                df = pd.read_csv(file_path, header=None)
            else:
                raise HTTPException(400, "Invalid file type")
        except Exception as e:
            raise HTTPException(400, f"Failed to read file: {e}")

        # Validate structure
        if df.shape[1] != 8:
            raise HTTPException(
                400,
                "Excel must have exactly 8 columns: "
                "Metric, Count, Day, Week, Month, Quarter, Halfyear, Year"
            )

        # Assign correct column names
        df.columns = [
            "description",
            "count",
            "day",
            "week",
            "month",
            "quarter",
            "halfyear",
            "year"
        ]

        # Insert rows
        for _, row in df.iterrows():
            all_records.append(
                InstockTrendData(
                    description=str(row["description"]),
                    count=str(row["count"]),
                    day=str(row["day"]),
                    week=str(row["week"]),
                    month=str(row["month"]),
                    quarter=str(row["quarter"]),
                    halfyear=str(row["halfyear"]),
                    year=str(row["year"]),
                    type=data_type,
                    upload_date=upload_date,
                    data_date=data_date
                )
            )

    if not all_records:
        raise HTTPException(400, "No valid data found")

    db.bulk_save_objects(all_records)
    db.commit()

    return {
        "message": "Files uploaded successfully",
        "upload_ids": upload_ids,
        "records_inserted": len(all_records)
    }


# -------------------- LIST UPLOADS --------------------
@router.get("/uploads/", response_model=List[dict])
def get_uploads(db: Session = Depends(get_db)):
    uploads = db.query(Indstocktrendupload).order_by(
        Indstocktrendupload.upload_date.desc()
    ).all()

    if not uploads:
        raise HTTPException(404, "No uploads found")

    return [
        {
            "id": u.id,
            "upload_date": u.upload_date,
            "data_date": u.data_date,
            "data_type": u.data_type,
            "file_name": u.file_name,
            "file_link": f"/indstocktrend/files/{u.id}"
        }
        for u in uploads
    ]


# -------------------- DOWNLOAD FILE --------------------
@router.get("/files/{upload_id}")
def download_file(upload_id: int, db: Session = Depends(get_db)):
    upload = db.query(Indstocktrendupload).filter(
        Indstocktrendupload.id == upload_id
    ).first()

    if not upload or not os.path.exists(upload.file_path):
        raise HTTPException(404, "File not found")

    return FileResponse(
        upload.file_path,
        filename=upload.file_name,
        media_type="application/octet-stream"
    )


# -------------------- GET LATEST DATA --------------------
@router.get("/stockdata/", response_model=Dict[str, Any])
def get_latest_stock_data(db: Session = Depends(get_db)):
    latest = db.query(Indstocktrendupload).order_by(
        desc(Indstocktrendupload.upload_date),
        desc(Indstocktrendupload.data_date)
    ).first()

    if not latest:
        raise HTTPException(404, "No uploads found")

    stocks = db.query(InstockTrendData).filter(
        InstockTrendData.upload_date == latest.upload_date,
        InstockTrendData.data_date == latest.data_date,
        InstockTrendData.type == latest.data_type
    ).order_by(InstockTrendData.id).all()

    if not stocks:
        raise HTTPException(404, "No stock data found")

    return {
        "upload_date": latest.upload_date,
        "data_date": latest.data_date,
        "type": latest.data_type,
        "stocks": [
            {
                "id": s.id,
                "description": s.description,
                "count": s.count,
                "day": s.day,
                "week": s.week,
                "month": s.month,
                "quarter": s.quarter,
                "halfyear": s.halfyear,
                "year": s.year
            }
            for s in stocks
        ]
    }


# -------------------- DELETE UPLOAD --------------------
@router.delete("/uploads/{upload_id}")
def delete_upload(upload_id: int, db: Session = Depends(get_db)):
    upload = db.query(Indstocktrendupload).filter(
        Indstocktrendupload.id == upload_id
    ).first()

    if not upload:
        raise HTTPException(404, "Upload not found")

    deleted_rows = db.query(InstockTrendData).filter(
        InstockTrendData.upload_date == upload.upload_date,
        InstockTrendData.data_date == upload.data_date,
        InstockTrendData.type == upload.data_type
    ).delete(synchronize_session=False)

    if upload.file_path and os.path.exists(upload.file_path):
        os.remove(upload.file_path)

    db.delete(upload)
    db.commit()

    return {
        "message": "Upload deleted successfully",
        "upload_id": upload_id,
        "rows_deleted": deleted_rows
    }
# -------------------- UPDATE UPLOAD --------------------
@router.put("/uploads/{upload_id}")
async def update_upload(
    upload_id: int,
    file: UploadFile = File(None),  # optional new file
    upload_date: date = Form(None),  # optional new upload date
    data_date: date = Form(None),    # optional new data date
    db: Session = Depends(get_db)
):
    # Fetch existing upload
    upload = db.query(Indstocktrendupload).filter(
        Indstocktrendupload.id == upload_id
    ).first()

    if not upload:
        raise HTTPException(404, "Upload not found")

    # Update dates if provided
    if upload_date:
        upload.upload_date = upload_date
    if data_date:
        upload.data_date = data_date

    # If a new file is provided, replace it
    if file:
        # Delete old file
        if upload.file_path and os.path.exists(upload.file_path):
            os.remove(upload.file_path)

        # Save new file
        filename = f"{date.today()}_{uuid4()}_{file.filename}"
        file_path = os.path.join(UPLOAD_FOLDER, filename)
        with open(file_path, "wb") as f:
            f.write(await file.read())

        # Update metadata
        upload.file_name = filename
        upload.file_path = file_path

        # Optional: re-read Excel/CSV and update InstockTrendData
        # Delete old data rows
        db.query(InstockTrendData).filter(
            InstockTrendData.upload_date == upload.upload_date,
            InstockTrendData.data_date == upload.data_date,
            InstockTrendData.type == upload.data_type
        ).delete(synchronize_session=False)

        # Read new file
        try:
            if filename.endswith((".xlsx", ".xls")):
                df = pd.read_excel(file_path, header=None)
            elif filename.endswith(".csv"):
                df = pd.read_csv(file_path, header=None)
            else:
                raise HTTPException(400, "Invalid file type")
        except Exception as e:
            raise HTTPException(400, f"Failed to read file: {e}")

        if df.shape[1] != 8:
            raise HTTPException(
                400,
                "Excel must have exactly 8 columns: "
                "Metric, Count, Day, Week, Month, Quarter, Halfyear, Year"
            )

        df.columns = [
            "description",
            "count",
            "day",
            "week",
            "month",
            "quarter",
            "halfyear",
            "year"
        ]

        # Insert new rows
        new_records = [
            InstockTrendData(
                description=str(row["description"]),
                count=str(row["count"]),
                day=str(row["day"]),
                week=str(row["week"]),
                month=str(row["month"]),
                quarter=str(row["quarter"]),
                halfyear=str(row["halfyear"]),
                year=str(row["year"]),
                type=upload.data_type,
                upload_date=upload.upload_date,
                data_date=upload.data_date
            )
            for _, row in df.iterrows()
        ]

        if new_records:
            db.bulk_save_objects(new_records)

    db.commit()
    db.refresh(upload)

    return {
        "message": "Upload updated successfully",
        "upload_id": upload.id,
        "file_name": upload.file_name,
        "upload_date": upload.upload_date,
        "data_date": upload.data_date,
        "records_inserted": len(new_records) if file else 0
    }
