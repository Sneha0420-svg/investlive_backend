# app/routers/stockpulse.py
import os
from uuid import uuid4
from datetime import date
from typing import List,Optional
import numpy as np
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
        return pd.read_csv(path, header=None)
    elif path.lower().endswith((".xls", ".xlsx")):
        return pd.read_excel(path, header=None)
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

        # Read file (NO HEADER)
        try:
            df = read_stockpulse_file(file_path)
        except Exception as e:
            raise HTTPException(400, f"Failed to read file: {e}")

        # Drop 32nd column (index 31)
        df = df.drop(df.columns[31], axis=1)

        # Validate column count
        if df.shape[1] != 32:
            raise HTTPException(
                400,
                f"Excel must have exactly 32 columns after cleanup, found {df.shape[1]}"
            )

        # Assign column names
        df.columns = [
            "scrip_code", "scrip", "co_code", "isin", "fv", "cmp",
            "dma_5", "dma_21", "dma_60", "dma_245",
            "wkh_52", "wkhdt_52",
            "wkl_52", "wkldt_52",
            "cur_vol",
            "dvma_5", "dvma_21", "dvma_60", "dvma_245",
            "wkhv_52", "wkhvdt_52",
            "wklv_52", "wklvdt_52",
            "myrh", "myrhdt",
            "myrl", "myrldt",
            "myruh", "myruhdt",
            "myrul", "myruldt",
            "pulse_score"
        ]

        # Replace NaN / 'nan' with None
        df = df.replace({np.nan: None, "nan": None, "NaN": None})

        # Date columns cleanup
        date_cols = [
            "wkhdt_52", "wkldt_52",
            "wkhvdt_52", "wklvdt_52",
            "myrhdt", "myrldt",
            "myruhdt", "myruldt"
        ]

        for col in date_cols:
            df[col] = pd.to_datetime(df[col], errors="coerce").dt.date
        df[date_cols] = df[date_cols].where(df[date_cols].notna(), None)

        # Insert rows
        for _, row in df.iterrows():
            all_records.append(
                StockPulseData(
                    scrip_code=str(row["scrip_code"]),
                    scrip=str(row["scrip"]),
                    co_code=str(row["co_code"]),
                    isin=str(row["isin"]),
                    fv=row["fv"],
                    cmp=row["cmp"],
                    dma_5=row["dma_5"],
                    dma_21=row["dma_21"],
                    dma_60=row["dma_60"],
                    dma_245=row["dma_245"],
                    wkh_52=row["wkh_52"],
                    wkhdt_52=row["wkhdt_52"],
                    wkl_52=row["wkl_52"],
                    wkldt_52=row["wkldt_52"],
                    cur_vol=row["cur_vol"],
                    dvma_5=row["dvma_5"],
                    dvma_21=row["dvma_21"],
                    dvma_60=row["dvma_60"],
                    dvma_245=row["dvma_245"],
                    wkhv_52=row["wkhv_52"],
                    wkhvdt_52=row["wkhvdt_52"],
                    wklv_52=row["wklv_52"],
                    wklvdt_52=row["wklvdt_52"],
                    myrh=row["myrh"],
                    myrhdt=row["myrhdt"],
                    myrl=row["myrl"],
                    myrldt=row["myrldt"],
                    myruh=row["myruh"],
                    myruhdt=row["myruhdt"],
                    myrul=row["myrul"],
                    myruldt=row["myruldt"],
                    pulse_score=row["pulse_score"],
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

# -------------------- GET STOCK BY ISIN --------------------
@router.get("/{isin}", response_model=StockPulseLatestResponse)
def get_stock_by_isin(isin: str, db: Session = Depends(get_db)):
    """
    Fetch all stockpulse data for a specific ISIN.
    """
    record = db.query(StockPulseData).filter(StockPulseData.isin == isin).first()
    
    if not record:
        raise HTTPException(404, f"No stock found with ISIN: {isin}")

    stock_dict = {c.name: getattr(record, c.name) for c in record.__table__.columns}

    return {
        "upload_date": record.upload_date,
        "data_date": record.data_date,
        "type": record.type,
        "records": [stock_dict]
    }

@router.put("/upload/{upload_id}")
async def update_stockpulse_upload(
    upload_id: int,
    files: Optional[List[UploadFile]] = File(None),  # ✅ optional now
    upload_date: date = Form(...),
    data_date: date = Form(...),
    data_type: str = Form(...),
    db: Session = Depends(get_db)
):
    # 1️⃣ Fetch the existing upload
    upload = db.query(StockPulseUpload).filter(
        StockPulseUpload.id == upload_id
    ).first()

    if not upload:
        raise HTTPException(404, "Upload not found")

    # 2️⃣ Delete old data rows for this upload
    db.query(StockPulseData).filter(
        StockPulseData.data_date == upload.data_date,
        StockPulseData.type == upload.data_type,
    ).delete(synchronize_session=False)

    all_records = []

    # Columns that require type conversion
    date_cols = [
        "wkhdt_52", "wkldt_52",
        "wkhvdt_52", "wklvdt_52",
        "myrhdt", "myrldt",
        "myruhdt", "myruldt"
    ]
    numeric_cols = [
        "fv", "cmp",
        "dma_5", "dma_21", "dma_60", "dma_245",
        "wkh_52", "wkl_52",
        "cur_vol",
        "dvma_5", "dvma_21", "dvma_60", "dvma_245",
        "wkhv_52", "wklv_52",
        "myrh", "myrl", "myruh", "myrul",
        "pulse_score"
    ]

    # 3️⃣ Process new files if any
    if files:
        # Delete old file only if replacing
        if os.path.exists(upload.file_path):
            os.remove(upload.file_path)

        for file in files:
            filename = f"{date.today()}_{uuid4()}_{file.filename}"
            file_path = os.path.join(UPLOAD_DIR, filename)

            # Save uploaded file
            with open(file_path, "wb") as f:
                f.write(await file.read())

            # Read file
            df = read_stockpulse_file(file_path)

            # Drop unwanted column and validate
            df = df.drop(df.columns[31], axis=1)
            if df.shape[1] != 32:
                raise HTTPException(400, "Excel must have exactly 32 columns after cleanup")

            # Assign column names
            df.columns = [
                "scrip_code", "scrip", "co_code", "isin", "fv", "cmp",
                "dma_5", "dma_21", "dma_60", "dma_245",
                "wkh_52", "wkhdt_52",
                "wkl_52", "wkldt_52",
                "cur_vol",
                "dvma_5", "dvma_21", "dvma_60", "dvma_245",
                "wkhv_52", "wkhvdt_52",
                "wklv_52", "wklvdt_52",
                "myrh", "myrhdt",
                "myrl", "myrldt",
                "myruh", "myruhdt",
                "myrul", "myruldt",
                "pulse_score"
            ]

            # Clean NaNs
            df = df.replace({np.nan: None, "nan": None, "NaN": None})

            # Convert date columns
            for col in date_cols:
                df[col] = pd.to_datetime(df[col], errors="coerce").dt.date
            df[date_cols] = df[date_cols].where(df[date_cols].notna(), None)

            # Convert numeric columns
            for col in numeric_cols:
                df[col] = pd.to_numeric(df[col], errors="coerce")
            df[numeric_cols] = df[numeric_cols].where(df[numeric_cols].notna(), None)

            # Insert rows
            for _, row in df.iterrows():
                all_records.append(
                    StockPulseData(
                        scrip_code=str(row["scrip_code"]),
                        scrip=str(row["scrip"]),
                        co_code=str(row["co_code"]),
                        isin=str(row["isin"]),
                        fv=row["fv"],
                        cmp=row["cmp"],
                        dma_5=row["dma_5"],
                        dma_21=row["dma_21"],
                        dma_60=row["dma_60"],
                        dma_245=row["dma_245"],
                        wkh_52=row["wkh_52"],
                        wkhdt_52=row["wkhdt_52"],
                        wkl_52=row["wkl_52"],
                        wkldt_52=row["wkldt_52"],
                        cur_vol=row["cur_vol"],
                        dvma_5=row["dvma_5"],
                        dvma_21=row["dvma_21"],
                        dvma_60=row["dvma_60"],
                        dvma_245=row["dvma_245"],
                        wkhv_52=row["wkhv_52"],
                        wkhvdt_52=row["wkhvdt_52"],
                        wklv_52=row["wklv_52"],
                        wklvdt_52=row["wklvdt_52"],
                        myrh=row["myrh"],
                        myrhdt=row["myrhdt"],
                        myrl=row["myrl"],
                        myrldt=row["myrldt"],
                        myruh=row["myruh"],
                        myruhdt=row["myruhdt"],
                        myrul=row["myrul"],
                        myruldt=row["myruldt"],
                        pulse_score=row["pulse_score"],
                        type=data_type,
                        upload_date=upload_date,
                        data_date=data_date
                    )
                )

        # Update upload metadata if file replaced
        upload.file_name = filename
        upload.file_path = file_path

    # 4️⃣ Update metadata even if no new file
    upload.upload_date = upload_date
    upload.data_date = data_date
    upload.data_type = data_type

    # 5️⃣ Save to DB
    if all_records:
        db.bulk_save_objects(all_records)

    db.commit()

    return {
        "message": "Upload updated successfully",
        "upload_id": upload.id,
        "records_inserted": len(all_records)
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
