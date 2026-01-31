# app/routers/stockpulse.py
import os
from uuid import uuid4
from datetime import date
from typing import List

import pandas as pd
from fastapi import APIRouter, Depends, UploadFile, File, Form, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from sqlalchemy import desc

from app.database import SessionLocal
from app.models.stockpulse import StockPulseData, StockPulseUpload
from app.schemas.stockpulse import StockPulseUploadSchema, StockPulseLatestResponse

UPLOAD_DIR = "uploads/stockpulse"
os.makedirs(UPLOAD_DIR, exist_ok=True)

router = APIRouter(prefix="/stockpulse", tags=["StockPulse"])


# -------------------- DB DEP --------------------
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# -------------------- FILE READER --------------------
def read_stockpulse_file(path: str) -> pd.DataFrame:
    if path.lower().endswith(".csv"):
        return pd.read_csv(path)
    elif path.lower().endswith((".xls", ".xlsx")):
        return pd.read_excel(path)
    else:
        raise HTTPException(400, "Only CSV, XLS, XLSX supported")


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
        file_path = os.path.join(UPLOAD_DIR, filename)

        # Save file
        with open(file_path, "wb") as f:
            f.write(await file.read())

        # Save upload metadata
        upload_record = StockPulseUpload(
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
        if df.shape[1] != 33:
            raise HTTPException(
                400,
                "Excel must have exactly 33 columns: "
                
            )

        # Assign correct column names
        df.columns = [
            "scrip_code",
            "scrip",
            "co_code",
            "isin",
            "fv",
            "cmp",
            "dma_5",
            "dma_21",
            "dma_60",
            "dma_245",
            "wkh_52",
            "wkhdt_52",
            "wkl_52",
            "wkldt_52",
            "cur_vol",
            "dvma_5",
            "dvma_21",
            "dvma_60",
            "dvma_245",
            "wkhv_52",
            "wkhvdt_52",
            "wklv_52",
            "wklvdt_52",
            "myrh",
            "myrhdt",
            "myrl",
            "myrldt",
            "myruh",
            "myruhdt",
            "myrul",
            "myruldt"
            
        ]

        # Insert rows
        for _, row in df.iterrows():
            all_records.append(
                StockPulseData(
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
@router.get("/uploads", response_model=List[StockPulseUploadSchema])
def list_uploads(db: Session = Depends(get_db)):
    uploads = db.query(StockPulseUpload).order_by(
        desc(StockPulseUpload.upload_date)
    ).all()

    return [
        {
            "id": u.id,
            "upload_date": u.upload_date,
            "data_date": u.data_date,
            "data_type": u.data_type,
            "file_name": u.file_name,
            "file_link": f"/stockpulse/files/{u.id}",
        }
        for u in uploads
    ]


# -------------------- DOWNLOAD --------------------
@router.get("/files/{upload_id}")
def download(upload_id: int, db: Session = Depends(get_db)):
    upload = db.query(StockPulseUpload).filter(
        StockPulseUpload.id == upload_id
    ).first()

    if not upload or not os.path.exists(upload.file_path):
        raise HTTPException(404, "File not found")

    return FileResponse(upload.file_path, filename=upload.file_name)


# -------------------- LATEST DATA --------------------
@router.get("/latest", response_model=StockPulseLatestResponse)
def latest_stockpulse(db: Session = Depends(get_db)):
    latest = db.query(StockPulseUpload).order_by(
        desc(StockPulseUpload.upload_date),
        desc(StockPulseUpload.data_date),
    ).first()

    if not latest:
        raise HTTPException(404, "No uploads found")

    records = db.query(StockPulseData).filter(
        StockPulseData.data_date == latest.data_date,
        StockPulseData.type == latest.data_type,
    ).all()

    return {
        "upload_date": latest.upload_date,
        "data_date": latest.data_date,
        "type": latest.data_type,
        "records": records,
    }


# -------------------- DELETE --------------------
@router.delete("/uploads/{upload_id}")
def delete_upload(upload_id: int, db: Session = Depends(get_db)):
    upload = db.query(StockPulseUpload).filter(
        StockPulseUpload.id == upload_id
    ).first()

    if not upload:
        raise HTTPException(404, "Upload not found")

    db.query(StockPulseData).filter(
        StockPulseData.data_date == upload.data_date,
        StockPulseData.type == upload.data_type,
    ).delete(synchronize_session=False)

    if os.path.exists(upload.file_path):
        os.remove(upload.file_path)

    db.delete(upload)
    db.commit()

    return {"message": "Deleted successfully"}
