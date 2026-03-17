import io
from datetime import date
from typing import List, Dict, Any

import pandas as pd
from fastapi import APIRouter, Depends, UploadFile, File, Form, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import desc
from fastapi.responses import StreamingResponse

from app.database import SessionLocal
from app.models.mostvalued import Mostvalued, MostValuedupload
from app.s3_utils import (
    upload_file_to_s3,
    delete_file_from_s3,
    get_s3_file_url,
    get_file_stream_from_s3
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
    housefile: UploadFile = File(...),
    stockfile: UploadFile = File(...),
    name1: str = Form(...),
    name2: str = Form(...),
    upload_date: date = Form(...),
    data_date: date = Form(...),
    data_type: str = Form(...),
    db: Session = Depends(get_db)
):
    all_records = []
    upload_ids = []

    async def process_file(file: UploadFile, name: str, ignore_second_col: bool = False):
        contents = await file.read()

        # Upload to S3
        s3_key = upload_file_to_s3(io.BytesIO(contents), "MostValuedHouse/Stock")

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

        # Read file
        try:
            if file.filename.endswith((".xlsx", ".xls")):
                df = pd.read_excel(io.BytesIO(contents), header=None)
            elif file.filename.endswith(".csv"):
                df = pd.read_csv(io.StringIO(contents.decode("utf-8")), header=None)
            else:
                raise HTTPException(400, "Invalid file type")
        except Exception as e:
            raise HTTPException(400, f"Failed to read file {file.filename}: {e}")

        # Remove 2nd column if needed (for stock files)
        if ignore_second_col:
            df.drop(df.columns[1], axis=1, inplace=True)

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

    # Process house file normally
    await process_file(housefile, name1)

    # Process stock file (ignore 2nd column)
    await process_file(stockfile, name2, ignore_second_col=True)

    db.bulk_save_objects(all_records)
    db.commit()

    return {
        "message": "Files uploaded successfully",
        "upload_ids": upload_ids,
        "records_inserted": len(all_records)
    }


# -------------------- LIST UPLOADS WITH PRESIGNED URL --------------------
@router.get("/uploads/", response_model=List[dict])
def get_uploads(db: Session = Depends(get_db)):
    uploads = db.query(MostValuedupload).order_by(
        MostValuedupload.upload_date.desc()
    ).all()

    return [
        {
            "id": u.id,
            "name": u.name,
            "upload_date": u.upload_date,
            "data_date": u.data_date,
            "data_type": u.data_type,
            "file_name": u.file_name,
            "file_url": get_s3_file_url(u.file_path)  # presigned URL for direct access
        }
        for u in uploads
    ]


# -------------------- DOWNLOAD FILE USING PRESIGNED URL --------------------
@router.get("/files/{upload_id}")
def get_file_presigned_url(upload_id: int, db: Session = Depends(get_db)):
    upload = db.query(MostValuedupload).filter(
        MostValuedupload.id == upload_id
    ).first()

    if not upload:
        raise HTTPException(404, "File not found")

    presigned_url = get_s3_file_url(upload.file_path)
    return {"file_name": upload.file_name, "url": presigned_url}


# -------------------- DOWNLOAD CSV FILE --------------------
@router.get("/download/{upload_id}")
def download_file(upload_id: int, db: Session = Depends(get_db)):
    # Fetch upload record
    upload = db.query(MostValuedupload).filter(
        MostValuedupload.id == upload_id
    ).first()
    if not upload:
        raise HTTPException(404, "File not found")

    # Get file stream from S3
    file_stream = get_file_stream_from_s3(upload.file_path)  # You need this function in s3_utils
    if not file_stream:
        raise HTTPException(404, "File not found in S3")

    # Ensure browser downloads with correct CSV name
    return StreamingResponse(
        file_stream,
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{upload.file_name}"'}
    )# -------------------- GET LATEST DATA (split by type) --------------------
@router.get("/latest/", response_model=Dict[str, Any])
def get_latest_stock_data(db: Session = Depends(get_db)):
    # Get the most recent upload
    latest_upload = db.query(MostValuedupload).order_by(
        desc(MostValuedupload.upload_date),
        desc(MostValuedupload.data_date)
    ).first()

    if not latest_upload:
        return {
            "upload_date": None,
            "data_date": None,
            "type": None,
            "stock": [],
            "house": []
        }

    # Fetch all stock data
    stock_records = db.query(Mostvalued).filter(
        Mostvalued.name == "stock",
        Mostvalued.data_date == latest_upload.data_date
    ).order_by(Mostvalued.id).all()

    # Fetch all house data
    house_records = db.query(Mostvalued).filter(
        Mostvalued.name == "house",
        Mostvalued.data_date == latest_upload.data_date
    ).order_by(Mostvalued.id).all()

    # Convert to dicts
    def map_records(records):
        return [
            {
                "id": r.id,
                "name": r.name,
                "company": r.company,
                "day": r.day,
                "week": r.week,
                "month": r.month,
                "quarter": r.quarter,
                "halfyear": r.halfyear,
                "year": r.year,
                "threeyear": r.threeyear
            }
            for r in records
        ]

    return {
        "upload_date": latest_upload.upload_date,
        "data_date": latest_upload.data_date,
        "type": latest_upload.data_type,
        "stock": map_records(stock_records),
        "house": map_records(house_records)
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
        Mostvalued.name == upload.name,
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

    # Store old values for deletion
    old_name = upload.name
    old_upload_date = upload.upload_date
    old_data_date = upload.data_date
    old_type = upload.data_type

    # Update upload fields
    if upload_date:
        upload.upload_date = upload_date
    if data_date:
        upload.data_date = data_date
    if name:
        upload.name = name

    new_records = []

    if file:
        # Delete old S3 file
        if upload.file_path:
            delete_file_from_s3(upload.file_path)

        # Upload new file to S3
        contents = await file.read()
        s3_key = upload_file_to_s3(io.BytesIO(contents), "MostValuedHouse/Stock")
        upload.file_name = file.filename
        upload.file_path = s3_key

        # Delete old Mostvalued records using old values
        db.query(Mostvalued).filter(
            Mostvalued.name == old_name,
            Mostvalued.data_date == old_data_date,
            Mostvalued.type == old_type
        ).delete(synchronize_session=False)

        # Read new file
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