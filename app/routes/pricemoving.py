# app/routes/pricemoving.py
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Query
from sqlalchemy.orm import Session
from sqlalchemy import func
from datetime import date, timedelta, datetime
import csv
import io

from app.models.pricemoving import PriceMoving
from app.database import SessionLocal
from app.s3_utils import upload_file_to_s3, get_s3_file_url  # S3 helper functions

router = APIRouter(prefix="/pricemoving", tags=["PriceMoving"])

# ----------------------
# DB Dependency
# ----------------------
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# ----------------------
# Upload CSV Data (No headers) -> S3
# Replace record if same ISIN + TRN_DATE exists
# Handles empty numeric fields safely
# ----------------------
@router.post("/upload")
async def upload_csv(file: UploadFile = File(...), db: Session = Depends(get_db)):
    if not file.filename.endswith(".csv"):
        raise HTTPException(status_code=400, detail="Only CSV files are allowed")

    content = await file.read()

    # Upload CSV to S3 under separate folder "price_moving"
    s3_key = upload_file_to_s3(io.BytesIO(content), folder="price_moving")
    s3_url = get_s3_file_url(s3_key)

    content_str = content.decode("utf-8").splitlines()
    reader = csv.reader(content_str)

    records_added = 0
    records_updated = 0

    for row in reader:
        if len(row) != 10:
            continue  # skip invalid rows
        try:
            trn_date = datetime.strptime(row[9].strip(), "%Y-%m-%d").date()
            isin = row[3].strip()

            # Use 0.0 as default for CMP if missing
            cmp_value = float(row[4].strip()) if row[4].strip() else 0.0
            dma_5 = float(row[5].strip()) if row[5].strip() else 0.0
            dma_21 = float(row[6].strip()) if row[6].strip() else 0.0
            dma_60 = float(row[7].strip()) if row[7].strip() else 0.0
            dma_245 = float(row[8].strip()) if row[8].strip() else 0.0

            existing = (
                db.query(PriceMoving)
                .filter(PriceMoving.ISIN == isin)
                .filter(PriceMoving.TRN_DATE == trn_date)
                .first()
            )

            if existing:
                # Update existing record
                existing.SCCODE = row[0].strip()
                existing.SCRIP = row[1].strip()
                existing.COCODE = row[2].strip()
                existing.CMP = cmp_value
                existing.DMA_5 = dma_5
                existing.DMA_21 = dma_21
                existing.DMA_60 = dma_60
                existing.DMA_245 = dma_245
                records_updated += 1
            else:
                # Insert new record
                pm = PriceMoving(
                    SCCODE=row[0].strip(),
                    SCRIP=row[1].strip(),
                    COCODE=row[2].strip(),
                    ISIN=isin,
                    CMP=cmp_value,
                    DMA_5=dma_5,
                    DMA_21=dma_21,
                    DMA_60=dma_60,
                    DMA_245=dma_245,
                    TRN_DATE=trn_date
                )
                db.add(pm)
                records_added += 1

        except Exception as e:
            print(f"Skipped row due to error: {row} -> {e}")
            continue

    db.commit()

    return {
        "message": "Upload completed",
        "records_inserted": records_added,
        "records_updated": records_updated,
        "file_url": s3_url
    }
# ----------------------
# Get last 2 years data for a specific ISIN
# ----------------------
@router.get("/graph/isin/{isin}")
def get_graph_data_by_isin(isin: str, db: Session = Depends(get_db)):
    two_years_ago = date.today() - timedelta(days=730)

    data = (
        db.query(PriceMoving)
        .filter(PriceMoving.ISIN == isin)
        .filter(PriceMoving.TRN_DATE >= two_years_ago)
        .order_by(PriceMoving.TRN_DATE)
        .all()
    )

    if not data:
        raise HTTPException(status_code=404, detail="Data not found for this ISIN")

    # Helper to convert None safely
    def safe_float(val):
        return float(val) if val is not None else None

    return {
        "dates": [d.TRN_DATE.isoformat() for d in data],
        "CMP": [safe_float(d.CMP) for d in data],
        "DMA_5": [safe_float(d.DMA_5) for d in data],
        "DMA_21": [safe_float(d.DMA_21) for d in data],
        "DMA_60": [safe_float(d.DMA_60) for d in data],
        "DMA_245": [safe_float(d.DMA_245) for d in data],
    }
# ----------------------
# Get all SCCODEs
# ----------------------
@router.get("/sccodes")
def get_sccodes(db: Session = Depends(get_db)):
    sccodes = db.query(PriceMoving.SCCODE, PriceMoving.SCRIP).distinct().all()
    return [{"SCCODE": s[0], "SCRIP": s[1]} for s in sccodes]

# ----------------------
# Get All PriceMoving Data (with pagination)
# ----------------------
@router.get("/all")
def get_all_data(limit: int = 1000, offset: int = 0, db: Session = Depends(get_db)):
    data = (
        db.query(PriceMoving)
        .order_by(PriceMoving.TRN_DATE.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )

    if not data:
        raise HTTPException(status_code=404, detail="No data found")

    return [
        {
            "ID": d.ID,
            "SCCODE": d.SCCODE,
            "SCRIP": d.SCRIP,
            "COCODE": d.COCODE,
            "ISIN": d.ISIN,
            "CMP": float(d.CMP),
            "DMA_5": float(d.DMA_5),
            "DMA_21": float(d.DMA_21),
            "DMA_60": float(d.DMA_60),
            "DMA_245": float(d.DMA_245),
            "TRN_DATE": d.TRN_DATE.isoformat(),
        }
        for d in data
    ]

# ----------------------
# Delete PriceMoving records for a specific TRN_DATE
# ----------------------
@router.delete("/delete")
def delete_by_trn_date(trn_date: str = Query(..., description="Date of the upload to delete"), db: Session = Depends(get_db)):
    try:
        date_obj = datetime.strptime(trn_date, "%Y-%m-%d").date()
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid date format. Use YYYY-MM-DD")

    existing = db.query(PriceMoving).filter(PriceMoving.TRN_DATE == date_obj).all()
    if not existing:
        raise HTTPException(status_code=404, detail="No records found for this date")

    deleted_count = db.query(PriceMoving).filter(PriceMoving.TRN_DATE == date_obj).delete(synchronize_session=False)
    db.commit()

    return {
        "message": f"Deleted {deleted_count} records for TRN_DATE {trn_date}"
    }

# ----------------------
# Get All Upload Dates (Grouped by TRN_DATE)
# ----------------------
@router.get("/uploads")
def get_all_uploads(db: Session = Depends(get_db)):
    uploads = (
        db.query(
            PriceMoving.TRN_DATE,
            func.count(PriceMoving.ID).label("total_records")
        )
        .group_by(PriceMoving.TRN_DATE)
        .order_by(PriceMoving.TRN_DATE.desc())
        .all()
    )

    if not uploads:
        raise HTTPException(status_code=404, detail="No uploads found")

    return [
        {
            "TRN_DATE": u.TRN_DATE.isoformat(),
            "TOTAL_RECORDS": u.total_records
        }
        for u in uploads
    ]