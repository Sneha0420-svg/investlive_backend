import os
import io
from datetime import date
from typing import List, Dict, Any
from uuid import uuid4

import pandas as pd
from fastapi import APIRouter, Depends, UploadFile, File, Form, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from sqlalchemy import desc

from app.database import SessionLocal
from app.models.mostvalued import Mostvalued, MostValuedupload  # your models

# Folder to store uploaded files
UPLOAD_FOLDER = "uploads/mostvalued"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

router = APIRouter(
    prefix="/mostvalued",
    tags=["MostValuedHouseStocks"]
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
    housefile: List[UploadFile] = File(...),
    stockfile: List[UploadFile] = File(...),
    name1: List[str] = Form(...),  # names for house files
    name2: List[str] = Form(...),  # names for stock files
    upload_date: date = Form(...),
    data_date: date = Form(...),
    data_type: str = Form(...),
    db: Session = Depends(get_db)
):
    # Ensure 1:1 mapping for both
    if len(housefile) != len(name1) or len(stockfile) != len(name2):
        raise HTTPException(400, "Each file must have a corresponding name")

    all_records = []
    upload_ids = []

    # -------- Process House Files --------
    for file, name in zip(housefile, name1):
        filename = f"{date.today()}_{uuid4()}_{file.filename}"
        file_path = os.path.join(UPLOAD_FOLDER, filename)

        # Save file
        with open(file_path, "wb") as f:
            f.write(await file.read())

        # Save metadata
        upload_record = MostValuedupload(
            name=name,
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

        # Read CSV/Excel
        if filename.endswith((".xlsx", ".xls")):
            df = pd.read_excel(file_path, header=None)
        elif filename.endswith(".csv"):
            df = pd.read_csv(file_path, header=None)
        else:
            raise HTTPException(400, "Invalid file type")

        if df.shape[1] != 8:
            raise HTTPException(
                400,
                "Excel must have exactly 8 columns: company, day, week, month, quarter, halfyear, year, threeyear"
            )

        df.columns = ["company", "day", "week", "month", "quarter", "halfyear", "year", "threeyear"]

        # Insert rows
        for _, row in df.iterrows():
            all_records.append(
                Mostvalued(
                    name=name,
                    company=row["company"],
                    day=float(row["day"]),
                    week=float(row["week"]),
                    month=float(row["month"]),
                    quarter=float(row["quarter"]),
                    halfyear=float(row["halfyear"]),
                    year=float(row["year"]),
                    threeyear=float(row["threeyear"]),
                    upload_date=upload_date,
                    data_date=data_date,
                    type=data_type
                )
            )

    # -------- Process Stock Files --------
    for file, name in zip(stockfile, name2):
        filename = f"{date.today()}_{uuid4()}_{file.filename}"
        file_path = os.path.join(UPLOAD_FOLDER, filename)

        # Save file
        with open(file_path, "wb") as f:
            f.write(await file.read())

        # Save metadata
        upload_record = MostValuedupload(
            name=name,
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

        # Read CSV/Excel
        if filename.endswith((".xlsx", ".xls")):
            df = pd.read_excel(file_path, header=None)
        elif filename.endswith(".csv"):
            df = pd.read_csv(file_path, header=None)
        else:
            raise HTTPException(400, "Invalid file type")

        if df.shape[1] != 8:
            raise HTTPException(
                400,
                "Excel must have exactly 8 columns: company, day, week, month, quarter, halfyear, year, threeyear"
            )

        df.columns = ["company", "day", "week", "month", "quarter", "halfyear", "year", "threeyear"]

        # Insert rows
        for _, row in df.iterrows():
            all_records.append(
                Mostvalued(
                    
                    name=name,
                    company=row["company"],
                    day=float(row["day"]),
                    week=float(row["week"]),
                    month=float(row["month"]),
                    quarter=float(row["quarter"]),
                    halfyear=float(row["halfyear"]),
                    year=float(row["year"]),
                    threeyear=float(row["threeyear"]),
                    upload_date=upload_date,
                    data_date=data_date,
                    type=data_type
                )
            )

    # Save all records to DB
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
    uploads = db.query(MostValuedupload).order_by(
        MostValuedupload.upload_date.desc()
    ).all()

    if not uploads:
        raise HTTPException(404, "No uploads found")

    return [
        {
            "id": u.id,
            "name":u.name,
            "upload_date": u.upload_date,
            "data_date": u.data_date,
            "data_type": u.data_type,
            "file_name": u.file_name,
            "file_link": f"/mostvalued/files/{u.id}"
        }
        for u in uploads
    ]


# -------------------- DOWNLOAD FILE --------------------
@router.get("/files/{upload_id}")
def download_file(upload_id: int, db: Session = Depends(get_db)):
    upload = db.query(MostValuedupload).filter(
        MostValuedupload.id == upload_id
    ).first()

    if not upload or not os.path.exists(upload.file_path):
        raise HTTPException(404, "File not found")

    return FileResponse(
        upload.file_path,
        filename=upload.file_name,
        media_type="application/octet-stream"
    )


# -------------------- GET LATEST DATA --------------------
@router.get("/latest/", response_model=Dict[str, Any])
def get_latest_stock_data(db: Session = Depends(get_db)):
    latest = db.query(MostValuedupload).order_by(
        desc(MostValuedupload.upload_date),
        desc(MostValuedupload.data_date)
    ).first()

    if not latest:
        raise HTTPException(404, "No uploads found")

    stocks = db.query(Mostvalued).filter(
        Mostvalued.upload_date == latest.upload_date,
        Mostvalued.data_date == latest.data_date,
        Mostvalued.type == latest.data_type
    ).order_by(Mostvalued.id).all()

    if not stocks:
        raise HTTPException(404, "No stock data found")

    return {
        "upload_date": latest.upload_date,
        "data_date": latest.data_date,
        "type": latest.data_type,
        "stocks": [
            {
                "id": s.id,
                "name": s.name,
                "company": s.company,
                "day": s.day,
                "week": s.week,
                "month": s.month,
                "quarter": s.quarter,
                "halfyear": s.halfyear,
                "year": s.year,
                "threeyear": s.threeyear
            }
            for s in stocks
        ]
    }


# -------------------- DELETE UPLOAD --------------------
@router.delete("/uploads/{upload_id}")
def delete_upload(upload_id: int, db: Session = Depends(get_db)):
    upload = db.query(MostValuedupload).filter(
        MostValuedupload.id == upload_id
    ).first()

    if not upload:
        raise HTTPException(404, "Upload not found")

    deleted_rows = db.query(Mostvalued).filter(
        Mostvalued.upload_date == upload.upload_date,
        Mostvalued.data_date == upload.data_date,
        Mostvalued.type == upload.data_type
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
    name: str = Form(None),         # optional new name
    upload_date: date = Form(None), # optional new upload date
    data_date: date = Form(None),   # optional new data date
    db: Session = Depends(get_db)
):
    # Fetch existing upload
    upload = db.query(MostValuedupload).filter(
        MostValuedupload.id == upload_id
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

        upload.file_name = filename
        upload.file_path = file_path

        # Delete old rows
        db.query(Mostvalued).filter(
            Mostvalued.upload_date == upload.upload_date,
            Mostvalued.data_date == upload.data_date,
            Mostvalued.type == upload.data_type
        ).delete(synchronize_session=False)

        # Read new Excel/CSV
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
                "Excel must have exactly 8 columns: company, day, week, month, quarter, halfyear, year, threeyear"
            )

        df.columns = ["company", "day", "week", "month", "quarter", "halfyear", "year", "threeyear"]

        new_records = [
            Mostvalued(
                name=name if name else upload.name,  # use new name if provided
                company=row["company"],
                day=float(row["day"]),
                week=float(row["week"]),
                month=float(row["month"]),
                quarter=float(row["quarter"]),
                halfyear=float(row["halfyear"]),
                year=float(row["year"]),
                threeyear=float(row["threeyear"]),
                upload_date=upload.upload_date,
                data_date=upload.data_date,
                type=upload.data_type
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
