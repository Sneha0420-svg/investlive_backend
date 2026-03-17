import io
from datetime import date
from uuid import uuid4
from fastapi import APIRouter, UploadFile, File, Form, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
import pandas as pd

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
    return None if val is None else str(val).strip()

def generate_s3_key(filename: str):
    return f"stocktrack/{uuid4()}_{filename}"

# -------------------- UPLOAD --------------------
@router.post("/upload")
async def upload_stocktrack(
    mkt_date: date = Form(...),
    file: UploadFile = File(...),
    db: Session = Depends(get_db)
):
    file_bytes = await file.read()

    # Upload to S3
    s3_key = upload_file_to_s3(io.BytesIO(file_bytes), generate_s3_key(file.filename))

    # Read file
    try:
        df = pd.read_excel(io.BytesIO(file_bytes), header=None)
    except Exception:
        try:
            df = pd.read_csv(io.StringIO(file_bytes.decode("utf-8")), header=None)
        except Exception:
            raise HTTPException(400, "Invalid file format")

    headers = ["ID","ISIN", "WK52", "MULTI_YR", "CIRCUIT", "MOBILITY", "TREND",
               "WK_BUST", "MTH_BUST", "QTR_BUST", "YR_BUST"]

    if df.shape[1] != len(headers):
        raise HTTPException(400, f"File must have {len(headers)} columns")

    df.columns = headers

    # Delete existing data for same date
    db.query(StockTrack).filter(StockTrack.mkt_date == mkt_date).delete()
    db.commit()

    # Insert records
    records = []
    for _, row in df.iterrows():
        if not row["ISIN"]:
            continue

        records.append(
            StockTrack(
                mkt_date=mkt_date,
                isin=safe_strip(row["ISIN"]),
                wk52=safe_strip(row["WK52"]),
                multi_yr=safe_strip(row["MULTI_YR"]),
                circuit=safe_strip(row["CIRCUIT"]),
                mobility=safe_strip(row["MOBILITY"]),
                trend=safe_strip(row["TREND"]),
                wk_bust=safe_strip(row["WK_BUST"]),
                mth_bust=safe_strip(row["MTH_BUST"]),
                qtr_bust=safe_strip(row["QTR_BUST"]),
                yr_bust=safe_strip(row["YR_BUST"]),
            )
        )

    if records:
        db.bulk_save_objects(records)
        db.commit()

    # Save upload record
    upload_row = StockTrackUpload(
        mkt_date=mkt_date,
        file_name=file.filename,
        file_path=s3_key
    )
    db.add(upload_row)
    db.commit()

    return {
        "message": "Uploaded successfully",
        "records": len(records)
    }

# -------------------- LIST --------------------
@router.get("/uploads")
def get_stocktrack_uploads(db: Session = Depends(get_db)):
    uploads = db.query(StockTrackUpload).order_by(StockTrackUpload.mkt_date.desc()).all()

    return [
        {
            "id": u.id,
            "mkt_date": u.mkt_date,
            "file_name": u.file_name,
            "download_url": f"/stocktrack/download/{u.id}"
        }
        for u in uploads
    ]

# -------------------- DOWNLOAD --------------------
@router.get("/download/{upload_id}")
def download_stocktrack_file(upload_id: int, db: Session = Depends(get_db)):
    upload = db.query(StockTrackUpload).filter(StockTrackUpload.id == upload_id).first()

    if not upload:
        raise HTTPException(404, "Upload not found")

    file_stream = get_file_stream_from_s3(upload.file_path)

    if not file_stream:
        raise HTTPException(404, "File not found in S3")

    # ✅ FIX: proper filename + type
    filename = upload.file_name.lower()

    if filename.endswith(".csv"):
        media_type = "text/csv"
    elif filename.endswith(".xlsx"):
        media_type = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    elif filename.endswith(".xls"):
        media_type = "application/vnd.ms-excel"
    else:
        media_type = "application/octet-stream"

    return StreamingResponse(
        file_stream,
        media_type=media_type,
        headers={
            "Content-Disposition": f'attachment; filename="{upload.file_name}"'
        }
    )

# -------------------- DELETE --------------------
@router.delete("/upload/{upload_id}")
def delete_stocktrack_upload(upload_id: int, db: Session = Depends(get_db)):
    upload = db.query(StockTrackUpload).filter(StockTrackUpload.id == upload_id).first()

    if not upload:
        raise HTTPException(404, "Upload not found")

    # ✅ delete stock data using mkt_date
    db.query(StockTrack).filter(
        StockTrack.mkt_date == upload.mkt_date
    ).delete(synchronize_session=False)

    # ✅ delete file from S3
    if upload.file_path:
        delete_file_from_s3(upload.file_path)

    # ✅ delete upload record
    db.delete(upload)
    db.commit()

    return {"message": "Deleted successfully"}

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


