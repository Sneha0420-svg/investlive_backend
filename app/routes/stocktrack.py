from fastapi import APIRouter, UploadFile, File, Depends, HTTPException
from sqlalchemy.orm import Session
from datetime import datetime
from typing import List, Optional
from uuid import uuid4
import io
import csv
import pandas as pd
from fastapi.responses import StreamingResponse

from app.database import SessionLocal
from app.models.stocktrack import StockTrack, StockTrackUpload
from app.s3_utils import upload_file_to_s3, delete_file_from_s3, get_file_stream_from_s3

router = APIRouter(prefix="/stocktrack", tags=["Stock Track"])

# -------------------- DB DEP --------------------
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
def safe_strip(val):
    if val is None:
        return None
    return str(val).strip()
# -------------------- UPLOAD CSV TO S3 --------------------
@router.post("/upload-csv")
async def upload_stocktrack_csv(
    mkt_date: str,
    file: UploadFile = File(...),
    db: Session = Depends(get_db)
):
    try:
        # Convert mkt_date string to date object
        mkt_date_obj = datetime.strptime(mkt_date, "%Y-%m-%d").date()

        # Upload file to S3
        s3_key = upload_file_to_s3(file.file, f"stocktrack/{uuid4()}_{file.filename}")

        # ------------------ DELETE ALL EXISTING DATA ------------------
        db.query(StockTrack).delete()
        db.commit()  # commit deletion before inserting new rows

        # ------------------ READ CSV FROM S3 ------------------
        s3_file = get_file_stream_from_s3(s3_key)
        df = pd.read_csv(io.StringIO(s3_file.read().decode("utf-8")), header=None)

        # Assign headers
        headers = ["ID","ISIN", "WK52", "MULTI_YR", "CIRCUIT", "MOBILITY", "TREND",
                   "WK_BUST", "MTH_BUST", "QTR_BUST", "YR_BUST"]
        df.columns = headers

        all_records = []
        for _, row in df.iterrows():
            if not row["ISIN"]:
                
                continue
            all_records.append(
                StockTrack(
                    mkt_date=mkt_date_obj,
                    isin=safe_strip(row["ISIN"]),
                    wk52=safe_strip(row["WK52"]),
                    multi_yr=safe_strip(row["MULTI_YR"]),
                    circuit=safe_strip(row["CIRCUIT"]),
                    mobility=safe_strip(row["MOBILITY"]),
                    trend=safe_strip(row["TREND"]),
                    wk_bust=safe_strip(row["WK_BUST"]),
                    mth_bust=safe_strip(row["MTH_BUST"]),
                    qtr_bust=safe_strip(row["QTR_BUST"]),
                    yr_bust=safe_strip(row["YR_BUST"])
                )
               )

        if all_records:
            db.bulk_save_objects(all_records)

        # Save upload record
        upload_record = StockTrackUpload(
            mkt_date=mkt_date_obj,
            file_name=file.filename,
            file_path=s3_key
        )
        db.add(upload_record)
        db.commit()

        return {"message": "Stock Track CSV uploaded and table replaced successfully"}

    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))


# -------------------- LIST ALL UPLOADS --------------------
@router.get("/uploads")
def get_all_uploads(db: Session = Depends(get_db)):
    uploads = db.query(StockTrackUpload).order_by(StockTrackUpload.mkt_date.desc()).all()
    return [
        {
            "id": u.id,
            "mkt_date": u.mkt_date,
            "file_name": u.file_name,
            "file_s3_url": f"/stocktrack/files/{u.id}"
        }
        for u in uploads
    ]


# -------------------- DOWNLOAD UPLOAD --------------------
@router.get("/files/{upload_id}")
def download_upload(upload_id: int, db: Session = Depends(get_db)):
    upload = db.query(StockTrackUpload).filter(StockTrackUpload.id == upload_id).first()
    if not upload or not upload.file_path:
        raise HTTPException(404, "File not found")

    s3_file = get_file_stream_from_s3(upload.file_path)
    return StreamingResponse(
        s3_file,
        media_type="application/octet-stream",
        headers={"Content-Disposition": f'attachment; filename="{upload.file_name}"'}
    )


# -------------------- GET ALL STOCKS --------------------
@router.get("/stocks")
def get_all_stocks(db: Session = Depends(get_db)):
    stocks = db.query(StockTrack).order_by(StockTrack.id).all()
    return [
        {
            "id": s.id,
            "mkt_date": s.mkt_date,
            "isin": s.isin,
            "wk52": s.wk52,
            "multi_yr": s.multi_yr,
            "circuit": s.circuit,
            "mobility": s.mobility,
            "trend": s.trend,
            "wk_bust": s.wk_bust,
            "mth_bust": s.mth_bust,
            "qtr_bust": s.qtr_bust,
            "yr_bust": s.yr_bust
        }
        for s in stocks
    ]


# -------------------- GET STOCK BY ISIN --------------------
@router.get("/stocks/{isin}")
def get_stock_by_isin(isin: str, db: Session = Depends(get_db)):
    stock = db.query(StockTrack).filter(StockTrack.isin == isin).first()
    if not stock:
        raise HTTPException(status_code=404, detail="Stock not found")
    return {
        "id": stock.id,
        "mkt_date": stock.mkt_date,
        "isin": stock.isin,
        "wk52": stock.wk52,
        "multi_yr": stock.multi_yr,
        "circuit": stock.circuit,
        "mobility": stock.mobility,
        "trend": stock.trend,
        "wk_bust": stock.wk_bust,
        "mth_bust": stock.mth_bust,
        "qtr_bust": stock.qtr_bust,
        "yr_bust": stock.yr_bust
    }


# -------------------- DELETE UPLOAD --------------------
@router.delete("/uploads/{upload_id}")
def delete_upload(upload_id: int, db: Session = Depends(get_db)):
    upload = db.query(StockTrackUpload).filter(StockTrackUpload.id == upload_id).first()
    if not upload:
        raise HTTPException(status_code=404, detail="Upload not found")

    # Delete related stock records
    db.query(StockTrack).filter(StockTrack.mkt_date == upload.mkt_date).delete(synchronize_session=False)

    # Delete file from S3
    if upload.file_path:
        delete_file_from_s3(upload.file_path)

    # Delete upload record
    db.delete(upload)
    db.commit()
    return {"message": f"Upload {upload_id} and its stocks deleted successfully"}