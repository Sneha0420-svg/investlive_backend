from fastapi import APIRouter, UploadFile, File, HTTPException, Depends, Form
from sqlalchemy.orm import Session
from datetime import date
from sqlalchemy import func
import pandas as pd
from datetime import datetime
from typing import List
import math
import io
from uuid import uuid4
import os
from app.database import SessionLocal
from app.models.ipo import DataUpload,IPOUpload
from app.schemas.ipo import DataUploadResponse, DataUploadUpdate,UploadSummaryResponse
from fastapi.responses import FileResponse


UPLOAD_FOLDER = os.getenv("UPLOAD_FOLDER", "uploads")

router = APIRouter(prefix="/IPO", tags=["IPO Data"])

# -------------------- Database Session --------------------
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# -------------------- Safe Date Parser --------------------
def parse_date_safe(date_str: str) -> datetime.date | None:
    if not date_str or pd.isna(date_str):
        return None
    for fmt in ("%d-%m-%Y", "%Y-%m-%d", "%d/%m/%Y"):
        try:
            return datetime.strptime(str(date_str), fmt).date()
        except ValueError:
            continue
    return None

# -------------------- Convert NaN to None --------------------
def convert_nan_to_none(obj):
    for attr in vars(obj):
        val = getattr(obj, attr)
        if isinstance(val, float) and math.isnan(val):
            setattr(obj, attr, None)
    return obj

def clean_objs(objs):
    return [convert_nan_to_none(obj) for obj in objs]

# -------------------- Upload Endpoint --------------------
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
        upload_record =IPOUpload(
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
                df = pd.read_excel(file_path)
            elif filename.endswith(".csv"):
                df = pd.read_csv(file_path)
            else:
                raise HTTPException(400, "Invalid file type")
        except Exception as e:
            raise HTTPException(400, f"Failed to read file: {e}")

        # Validate structure
        if df.shape[1] != 47:
            raise HTTPException(
                400,
                "Excel must have exactly 47 columns: "
                "Metric, Count, Day, Week, Month, Quarter, Halfyear, Year"
            )

        # Assign correct column names
        df.columns = [
            "ISIN", "CO_NAME", "IBR_NAME", "ISS_OPEN", "ISS_CLOSE", "ALLOTMENT_DATE", "REFUND_DT", 
            "DEMAT_DT", "TRADING_DT", "HIGH", "LOW", "OFF_PRICE", "FACE_VALUE", "ISS_AMT", 
            "ISS_QTY", "LISTED_PR", "LISTED_GAIN", "LISTED_DT", "MKT_LOT", "SUBS_TIMES", "EXCH",
            "ISS_TYPE", "OFFER_TYPE", "OFFER_OBJECTIVE", "STATE", "SIGNED_BY", "INDUSTRY",
            "LM1", "LM2", "LM3", "LM4", "LM5", "LM6", "LM7", "LM8", "LM9", "LM10", "LM11", "LM12",
            "LM13", "LM14", "LM15", "MKTMKR1", "MKTMKR2", "MKTMKR3", "MKTMKR4", "MKTMKR5"
        ]
        date_cols = [
            "ISS_OPEN", "ISS_CLOSE", "ALLOTMENT_DATE",
            "REFUND_DT", "DEMAT_DT", "TRADING_DT", "LISTED_DT"
        ]

        for col in date_cols:
            if col in df.columns:
                df[col] = df[col].apply(parse_date_safe)
        df = df.where(pd.notnull(df), None)

        # Insert rows
        for _, row in df.iterrows():
            all_records.append(
                DataUpload(
                isin=row.get("ISIN"),
                co_name=row.get("CO_NAME"),
                ibr_name=row.get("IBR_NAME"),
                iss_open=row.get("ISS_OPEN"),
                iss_close=row.get("ISS_CLOSE"),
                allotment_date=row.get("ALLOTMENT_DATE"),
                refund_dt=row.get("REFUND_DT"),
                demat_dt=row.get("DEMAT_DT"),
                trading_dt=row.get("TRADING_DT"),
                high=row.get("HIGH"),
                low=row.get("LOW"),
                off_price=row.get("OFF_PRICE"),
                face_value=row.get("FACE_VALUE"),
                iss_amt=row.get("ISS_AMT"),
                iss_qty=row.get("ISS_QTY"),
                listed_pr=row.get("LISTED_PR"),
                listed_gain=row.get("LISTED_GAIN"),
                listed_dt=row.get("LISTED_DT"),
                mkt_lot=row.get("MKT_LOT"),
                subs_times=row.get("SUBS_TIMES"),
                exch=row.get("EXCH"),
                iss_type=row.get("ISS_TYPE"),
                offer_type=row.get("OFFER_TYPE"),
                offer_objective=row.get("OFFER_OBJECTIVE"),
                state=row.get("STATE"),
                signed_by=row.get("SIGNED_BY"),
                industry=row.get("INDUSTRY"),
                lm1=row.get("LM1"),
                lm2=row.get("LM2"),
                lm3=row.get("LM3"),
                lm4=row.get("LM4"),
                lm5=row.get("LM5"),
                lm6=row.get("LM6"),
                lm7=row.get("LM7"),
                lm8=row.get("LM8"),
                lm9=row.get("LM9"),
                lm10=row.get("LM10"),
                lm11=row.get("LM11"),
                lm12=row.get("LM12"),
                lm13=row.get("LM13"),
                lm14=row.get("LM14"),
                lm15=row.get("LM15"),
                mktmkr1=row.get("MKTMKR1"),
                mktmkr2=row.get("MKTMKR2"),
                mktmkr3=row.get("MKTMKR3"),
                mktmkr4=row.get("MKTMKR4"),
                mktmkr5=row.get("MKTMKR5"),
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


# -------------------- GET All Uploads --------------------
@router.get("/uploads", response_model=List[UploadSummaryResponse])
def get_uploads_summary(db: Session = Depends(get_db)):
    uploads = db.query(IPOUpload).order_by(IPOUpload.upload_date.desc()).all()

    return [
        {
            "id": u.id,
            "upload_date": u.upload_date,
            "data_date": u.data_date,
            "data_type": u.data_type,
            "file_name": u.file_name,
            "file_link": f"/IPO/files/{u.id}"
        }
        for u in uploads
    ]


# -------------------- GET Latest--------------------
@router.get("/latest")
def get_latest_all(db: Session = Depends(get_db)):

    # 1️⃣ get latest upload_date
    latest_upload = db.query(
        DataUpload.upload_date,
        DataUpload.data_date
    ).order_by(DataUpload.upload_date.desc()).first()

    if not latest_upload:
        raise HTTPException(status_code=404, detail="No data found")

    # 2️⃣ fetch all rows for that upload_date & data_date
    rows = db.query(DataUpload).filter(
        DataUpload.upload_date == latest_upload.upload_date,
        DataUpload.data_date == latest_upload.data_date
    ).order_by(DataUpload.isin).all()

    return {
        "upload_date": latest_upload.upload_date,
        "data_date": latest_upload.data_date,
        "data": clean_objs(rows)
    }

# -------------------- Download Upload File --------------------
@router.get("/files/{upload_id}")
def download_file(upload_id: int, db: Session = Depends(get_db)):
    # Fetch upload record
    upload = db.query(IPOUpload).filter(IPOUpload.id == upload_id).first()
    if not upload:
        raise HTTPException(status_code=404, detail="Upload not found")
    
    # Check if file exists
    if not upload.file_path or not os.path.exists(upload.file_path):
        raise HTTPException(status_code=404, detail="File not found on server")

    # Return file as download
    return FileResponse(
        path=upload.file_path,
        filename=upload.file_name,
        media_type="application/octet-stream"
    )

# -------------------- Update Upload --------------------
@router.put("/upload/{upload_id}", response_model=UploadSummaryResponse)
async def update_upload(
    upload_id: int,
    db: Session = Depends(get_db),
    file: UploadFile = File(None),
    upload_date: date | None = Form(None),
    data_date: date | None = Form(None),
    data_type: str | None = Form(None)
):
    # 1️⃣ Fetch upload record
    upload = db.query(IPOUpload).filter(IPOUpload.id == upload_id).first()
    if not upload:
        raise HTTPException(status_code=404, detail="Upload not found")
    
    # 2️⃣ Update metadata
    if upload_date:
        upload.upload_date = upload_date
    if data_date:
        upload.data_date = data_date
    if data_type:
        upload.data_type = data_type

    records_inserted = 0

    # 3️⃣ If a new file is uploaded, replace old file and update DataUpload rows
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

        # Delete old DataUpload rows
        db.query(DataUpload).filter(DataUpload.upload_id == upload_id).delete(synchronize_session=False)

        # Read new file (Excel or CSV)
        try:
            if filename.endswith((".xlsx", ".xls")):
                df = pd.read_excel(file_path)
            elif filename.endswith(".csv"):
                df = pd.read_csv(file_path)
            else:
                raise HTTPException(400, "Invalid file type")
        except Exception as e:
            raise HTTPException(400, f"Failed to read file: {e}")

        # Validate columns
        if df.shape[1] != 47:
            raise HTTPException(400, "File must have exactly 47 columns")

        df.columns = [
            "ISIN", "CO_NAME", "IBR_NAME", "ISS_OPEN", "ISS_CLOSE", "ALLOTMENT_DATE", "REFUND_DT", 
            "DEMAT_DT", "TRADING_DT", "HIGH", "LOW", "OFF_PRICE", "FACE_VALUE", "ISS_AMT", 
            "ISS_QTY", "LISTED_PR", "LISTED_GAIN", "LISTED_DT", "MKT_LOT", "SUBS_TIMES", "EXCH",
            "ISS_TYPE", "OFFER_TYPE", "OFFER_OBJECTIVE", "STATE", "SIGNED_BY", "INDUSTRY",
            "LM1", "LM2", "LM3", "LM4", "LM5", "LM6", "LM7", "LM8", "LM9", "LM10", "LM11", "LM12",
            "LM13", "LM14", "LM15", "MKTMKR1", "MKTMKR2", "MKTMKR3", "MKTMKR4", "MKTMKR5"
        ]

        # Parse date columns
        date_cols = ["ISS_OPEN", "ISS_CLOSE", "ALLOTMENT_DATE", "REFUND_DT", "DEMAT_DT", "TRADING_DT", "LISTED_DT"]
        for col in date_cols:
            df[col] = df[col].apply(parse_date_safe)

        # Insert new DataUpload rows
        new_records = []
        for _, row in df.iterrows():
            new_records.append(DataUpload(
                upload_id=upload_id,
                isin=row.get("ISIN"),
                co_name=row.get("CO_NAME"),
                ibr_name=row.get("IBR_NAME"),
                iss_open=row.get("ISS_OPEN"),
                iss_close=row.get("ISS_CLOSE"),
                allotment_date=row.get("ALLOTMENT_DATE"),
                refund_dt=row.get("REFUND_DT"),
                demat_dt=row.get("DEMAT_DT"),
                trading_dt=row.get("TRADING_DT"),
                high=row.get("HIGH"),
                low=row.get("LOW"),
                off_price=row.get("OFF_PRICE"),
                face_value=row.get("FACE_VALUE"),
                iss_amt=row.get("ISS_AMT"),
                iss_qty=row.get("ISS_QTY"),
                listed_pr=row.get("LISTED_PR"),
                listed_gain=row.get("LISTED_GAIN"),
                listed_dt=row.get("LISTED_DT"),
                mkt_lot=row.get("MKT_LOT"),
                subs_times=row.get("SUBS_TIMES"),
                exch=row.get("EXCH"),
                iss_type=row.get("ISS_TYPE"),
                offer_type=row.get("OFFER_TYPE"),
                offer_objective=row.get("OFFER_OBJECTIVE"),
                state=row.get("STATE"),
                signed_by=row.get("SIGNED_BY"),
                industry=row.get("INDUSTRY"),
                lm1=row.get("LM1"),
                lm2=row.get("LM2"),
                lm3=row.get("LM3"),
                lm4=row.get("LM4"),
                lm5=row.get("LM5"),
                lm6=row.get("LM6"),
                lm7=row.get("LM7"),
                lm8=row.get("LM8"),
                lm9=row.get("LM9"),
                lm10=row.get("LM10"),
                lm11=row.get("LM11"),
                lm12=row.get("LM12"),
                lm13=row.get("LM13"),
                lm14=row.get("LM14"),
                lm15=row.get("LM15"),
                mktmkr1=row.get("MKTMKR1"),
                mktmkr2=row.get("MKTMKR2"),
                mktmkr3=row.get("MKTMKR3"),
                mktmkr4=row.get("MKTMKR4"),
                mktmkr5=row.get("MKTMKR5"),
                upload_date=upload.upload_date,
                data_date=upload.data_date
            ))
        if new_records:
            db.bulk_save_objects(new_records)
            records_inserted = len(new_records)

    db.commit()
    db.refresh(upload)

    return {
        "message": "Upload updated successfully",
        "upload_id": upload.id,
        "file_name": upload.file_name,
        "upload_date": upload.upload_date,
        "data_date": upload.data_date,
        "records_inserted": records_inserted
    }



# -------------------- Delete Upload --------------------
@router.delete("/upload/{upload_id}")
def delete_upload(upload_id: int, db: Session = Depends(get_db)):
    upload = db.query(IPOUpload).filter(IPOUpload.id == upload_id).first()
    if not upload:
        raise HTTPException(status_code=404, detail="Upload not found")

    # delete related ipo data rows
    db.query(DataUpload).filter(
        DataUpload.upload_date == upload.upload_date,
        DataUpload.data_date == upload.data_date
    ).delete(synchronize_session=False)

    # delete upload record
    db.delete(upload)
    db.commit()

    return {"detail": "Upload and related IPO data deleted successfully"}
