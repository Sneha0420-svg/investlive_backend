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
from app.models.mostvalued import Mostvalued, MostValuedupload
from app.s3_utils import (
    upload_file_to_s3,
    delete_file_from_s3,
    get_file_stream_from_s3,
    get_s3_file_url
)

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


# -------------------- UPLOAD FILES --------------------
@router.post("/upload")
async def upload_multiple_data(
    housefile: List[UploadFile] = File(...),
    stockfile: List[UploadFile] = File(...),
    name1: List[str] = Form(...),
    name2: List[str] = Form(...),
    upload_date: date = Form(...),
    data_date: date = Form(...),
    data_type: str = Form(...),
    db: Session = Depends(get_db)
):
    # Ensure 1:1 mapping
    if len(housefile) != len(name1) or len(stockfile) != len(name2):
        raise HTTPException(400, "Each file must have a corresponding name")

    all_records = []
    upload_ids = []

    # Helper to process files
    async def process_file(file: UploadFile, name: str):
        contents = await file.read()
        s3_key = upload_file_to_s3(io.BytesIO(contents), "mostvalued")

        upload_record = MostValuedupload(
            name=name,
            upload_date=upload_date,
            data_date=data_date,
            data_type=data_type,
            file_name=file.filename,
            file_path=s3_key
        )
        db.add(upload_record)
        db.commit()
        db.refresh(upload_record)
        upload_ids.append(upload_record.id)

        # Read file into DataFrame
        try:
            if file.filename.endswith((".xlsx", ".xls")):
                df = pd.read_excel(io.BytesIO(contents), header=None)
            elif file.filename.endswith(".csv"):
                df = pd.read_csv(io.StringIO(contents.decode("utf-8")), header=None)
            else:
                raise HTTPException(400, "Invalid file type")
        except Exception as e:
            raise HTTPException(400, f"Failed to read file {file.filename}: {e}")

        if df.shape[1] != 8:
            raise HTTPException(
                400,
                "File must have exactly 8 columns: company, day, week, month, quarter, halfyear, year, threeyear"
            )

        df.columns = ["company", "day", "week", "month", "quarter", "halfyear", "year", "threeyear"]

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

    # Process all house files
    for file, name in zip(housefile, name1):
        await process_file(file, name)

    # Process all stock files
    for file, name in zip(stockfile, name2):
        await process_file(file, name)

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
            "name": u.name,
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

    if not upload:
        raise HTTPException(404, "File not found")

    file_stream = get_file_stream_from_s3(upload.file_path)
    return StreamingResponse(
        file_stream,
        media_type="application/octet-stream",
        headers={"Content-Disposition": f'attachment; filename="{upload.file_name}"'}
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

    if upload.file_path:
        delete_file_from_s3(upload.file_path)

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
    file: UploadFile = File(None),
    name: str = Form(None),
    upload_date: date = Form(None),
    data_date: date = Form(None),
    db: Session = Depends(get_db)
):
    upload = db.query(MostValuedupload).filter(
        MostValuedupload.id == upload_id
    ).first()

    if not upload:
        raise HTTPException(404, "Upload not found")

    if upload_date:
        upload.upload_date = upload_date
    if data_date:
        upload.data_date = data_date
    if name:
        upload.name = name

    new_records = []

    if file:
        # Delete old file
        if upload.file_path:
            delete_file_from_s3(upload.file_path)

        # Upload new file to S3
        contents = await file.read()
        s3_key = upload_file_to_s3(io.BytesIO(contents), "mostvalued")
        upload.file_name = file.filename
        upload.file_path = s3_key

        # Delete old records
        db.query(Mostvalued).filter(
            Mostvalued.upload_date == upload.upload_date,
            Mostvalued.data_date == upload.data_date,
            Mostvalued.type == upload.data_type
        ).delete(synchronize_session=False)

        # Read new file into DataFrame
        try:
            if file.filename.endswith((".xlsx", ".xls")):
                df = pd.read_excel(io.BytesIO(contents), header=None)
            elif file.filename.endswith(".csv"):
                df = pd.read_csv(io.StringIO(contents.decode("utf-8")), header=None)
            else:
                raise HTTPException(400, "Invalid file type")
        except Exception as e:
            raise HTTPException(400, f"Failed to read file: {e}")

        if df.shape[1] != 8:
            raise HTTPException(
                400,
                "File must have exactly 8 columns: company, day, week, month, quarter, halfyear, year, threeyear"
            )

        df.columns = ["company", "day", "week", "month", "quarter", "halfyear", "year", "threeyear"]

        # Prepare new DB records
        new_records = [
            Mostvalued(
                name=name if name else upload.name,
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