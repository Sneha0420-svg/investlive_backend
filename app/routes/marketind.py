from fastapi import APIRouter, Depends, UploadFile, File, HTTPException, Form
from sqlalchemy import func
from sqlalchemy.orm import Session
from typing import List, Dict, Any
from datetime import date
import pandas as pd
import io
import math

from app.models.marketind import StockData, MarketIndicatorUpload
from app.database import SessionLocal
from app.s3_utils import (
    upload_file_to_s3,
    delete_file_from_s3,
    get_file_stream_from_s3
)

router = APIRouter(tags=["Market Indicator"])


# ---------------- DB Session ----------------
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# ---------------- Helpers ----------------
def safe_int(value, default=0):
    try:
        if value is None or (isinstance(value, float) and math.isnan(value)):
            return default
        return int(value)
    except Exception:
        return default


def safe_float(value, default=0.0):
    try:
        if value is None or (isinstance(value, float) and math.isnan(value)):
            return default
        return float(value)
    except Exception:
        return default


# ======================================================
# Upload Multiple Files
# ======================================================
@router.post("/upload-data-multiple/")
async def upload_multiple_data(
    files: List[UploadFile] = File(...),
    mkt_date: date = Form(...),
    db: Session = Depends(get_db)
):

    all_inserted = []

    # Delete existing records for same date
    existing_count = db.query(StockData).filter(
        StockData.mkt_date == mkt_date
    ).delete(synchronize_session=False)

    db.commit()

    for file in files:

        contents = await file.read()

        # Upload file to S3
        s3_key = upload_file_to_s3(io.BytesIO(contents), "market_indicator")

        upload_record = MarketIndicatorUpload(
            mkt_date=mkt_date,
            file_name=file.filename,
            file_path=s3_key
        )

        db.add(upload_record)
        db.commit()
        db.refresh(upload_record)

        # Read dataframe
        try:
            if file.filename.endswith((".xlsx", ".xls")):
                df = pd.read_excel(io.BytesIO(contents), header=None)
            elif file.filename.endswith(".csv"):
                df = pd.read_csv(io.StringIO(contents.decode("utf-8")), header=None)
            else:
                raise HTTPException(400, f"Invalid file type: {file.filename}")
        except Exception as e:
            raise HTTPException(400, f"Failed to read file {file.filename}: {e}")

        if df.shape[1] < 9:
            raise HTTPException(400, f"{file.filename} must have at least 9 columns")

        df.columns = [
            "name",
            "yr_ago",
            "curnt",
            "ch",
            "H_ID",
            "S_ID",
            "IDX_ID",
            "flag",
            "ID"
        ]

        records = []

        for _, row in df.iterrows():
            stock = StockData(
                name=str(row["name"]).strip() if row["name"] else "",
                yr_ago=safe_float(row["yr_ago"]),
                curnt=safe_float(row["curnt"]),
                ch=safe_float(row["ch"]),
                H_ID=safe_int(row["H_ID"]),
                S_ID=safe_int(row["S_ID"]),
                IDX_ID=safe_int(row["IDX_ID"]),
                flag=str(row["flag"]).strip() if row["flag"] else "",
                ID=safe_int(row["ID"]),
                mkt_date=mkt_date
            )
            records.append(stock)

        db.bulk_save_objects(records)
        db.commit()

        all_inserted.append({
            "file": file.filename,
            "records_inserted": len(records),
            "upload_id": upload_record.id
        })

    return {
        "message": f"{len(files)} files processed successfully. Existing rows deleted: {existing_count}",
        "details": all_inserted
    }


# ======================================================
# Get Upload History
# ======================================================
@router.get("/marketindicator/uploads/")
def get_uploads(db: Session = Depends(get_db)):

    uploads = db.query(MarketIndicatorUpload)\
        .order_by(MarketIndicatorUpload.mkt_date.desc()).all()

    if not uploads:
        raise HTTPException(404, "No uploads found")

    return uploads


# ======================================================
# Download Uploaded File
# ======================================================
@router.get("/files/{upload_id}")
def download_file(upload_id: int, db: Session = Depends(get_db)):

    record = db.query(MarketIndicatorUpload)\
        .filter(MarketIndicatorUpload.id == upload_id).first()

    if not record:
        raise HTTPException(404, "File not found")

    return get_file_stream_from_s3(record.file_path)


# ======================================================
# Latest Market Indicator Data
# ======================================================
def is_header_row(stock: StockData) -> bool:
    numeric_fields = [stock.yr_ago, stock.curnt, stock.ch, stock.S_ID, stock.IDX_ID]
    return all(f is None or f == 0 for f in numeric_fields)


@router.get("/marketindicator/latest/", response_model=Dict[str, Any])
def get_latest_marketindicator(db: Session = Depends(get_db)):

    latest_date = db.query(func.max(StockData.mkt_date)).scalar()

    if not latest_date:
        raise HTTPException(404, "No stock data found")

    stocks = db.query(StockData)\
        .filter(StockData.mkt_date == latest_date)\
        .order_by(StockData.H_ID, StockData.ID).all()

    tab_map = {
        1: "Returns",
        2: "Indices",
        3: "Currencies",
        4: "World P/E Ratio",
        5: "Commodities"
    }

    tab_sections = {
        1: ["India Stocks", "Bullion", "Forex vs INR", "Crude"],
        2: ["BRICS", "Asia/Pacific", "America/Europe"],
        3: ["INR vs.", "USD vs."],
        4: ["Country"],
        5: ["Metals (Kg)", "Agro-Cons (100 Kg)", "Agro-Indu (100 Kg)", "Energy (Rs)"]
    }

    result = {tab: [] for tab in tab_map.values()}
    current_section_per_tab = {}

    for stock in stocks:

        tab_name = tab_map.get(stock.H_ID, "Unknown")
        stock_name = (stock.name or "").strip()

        sections_for_tab = tab_sections.get(stock.H_ID, [])

        is_header = stock_name in sections_for_tab or is_header_row(stock)

        if is_header:
            section = {"title": stock_name, "rows": []}
            result[tab_name].append(section)
            current_section_per_tab[tab_name] = section
        else:
            current_section = current_section_per_tab.get(tab_name)

            if not current_section:
                current_section = {"title": "(No Title)", "rows": []}
                result[tab_name].append(current_section)
                current_section_per_tab[tab_name] = current_section

            current_section["rows"].append([
                stock.name,
                stock.yr_ago,
                stock.curnt,
                stock.ch,
                stock.H_ID,
                stock.S_ID,
                stock.IDX_ID
            ])

    return {
        "latest_mkt_date": latest_date,
        "total_records": len(stocks),
        "stocks_by_tab": result
    }


# ======================================================
# Get Stocks by IDX_ID
# ======================================================
@router.get("/marketindicator/idx/{idx_id}")
def get_stocks_by_idx(idx_id: int, db: Session = Depends(get_db)):

    latest_date = db.query(func.max(StockData.mkt_date))\
        .filter(StockData.IDX_ID == idx_id).scalar()

    if not latest_date:
        raise HTTPException(404, f"No stock data found for IDX_ID {idx_id}")

    stocks = db.query(StockData)\
        .filter(
            StockData.IDX_ID == idx_id,
            StockData.mkt_date == latest_date
        ).order_by(StockData.H_ID, StockData.ID).all()

    return stocks


# ======================================================
# Delete Upload
# ======================================================
@router.delete("/marketindicator/uploads/{upload_id}")
def delete_upload(upload_id: int, db: Session = Depends(get_db)):

    upload = db.query(MarketIndicatorUpload)\
        .filter(MarketIndicatorUpload.id == upload_id).first()

    if not upload:
        raise HTTPException(404, "Upload not found")

    deleted_rows = db.query(StockData)\
        .filter(StockData.mkt_date == upload.mkt_date)\
        .delete(synchronize_session=False)

    delete_file_from_s3(upload.file_path)

    db.delete(upload)
    db.commit()

    return {
        "message": "Upload deleted successfully",
        "stocks_deleted": deleted_rows
    }