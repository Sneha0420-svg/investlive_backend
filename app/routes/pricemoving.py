# app/routes/pricemoving.py
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from sqlalchemy.orm import Session
from datetime import date, timedelta
import csv
from io import StringIO

from app.models.pricemoving import PriceMoving
from app.database import SessionLocal
from datetime import datetime


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
# Upload CSV Data (No headers)
# Replace record if same ISIN + TRN_DATE exists
# ----------------------
@router.post("/upload")
def upload_csv(file: UploadFile = File(...), db: Session = Depends(get_db)):
    if not file.filename.endswith(".csv"):
        raise HTTPException(status_code=400, detail="Only CSV files are allowed")

    content = file.file.read().decode("utf-8").splitlines()
    reader = csv.reader(content)

    records_added = 0
    records_updated = 0

    for row in reader:
        if len(row) != 10:
            continue  # skip invalid rows

        try:
            trn_date = datetime.strptime(row[9].strip(), "%Y-%m-%d").date()
            isin = row[3].strip()

            # 🔎 Check if record already exists
            existing = (
                db.query(PriceMoving)
                .filter(PriceMoving.ISIN == isin)
                .filter(PriceMoving.TRN_DATE == trn_date)
                .first()
            )

            if existing:
                # ✅ Update existing record
                existing.SCCODE = row[0].strip()
                existing.SCRIP = row[1].strip()
                existing.COCODE = row[2].strip()
                existing.CMP = float(row[4])
                existing.DMA_5 = float(row[5])
                existing.DMA_21 = float(row[6])
                existing.DMA_60 = float(row[7])
                existing.DMA_245 = float(row[8])

                records_updated += 1
            else:
                # ✅ Insert new record
                pm = PriceMoving(
                    SCCODE=row[0].strip(),
                    SCRIP=row[1].strip(),
                    COCODE=row[2].strip(),
                    ISIN=isin,
                    CMP=float(row[4]),
                    DMA_5=float(row[5]),
                    DMA_21=float(row[6]),
                    DMA_60=float(row[7]),
                    DMA_245=float(row[8]),
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
        "records_updated": records_updated
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

    return {
        "dates": [d.TRN_DATE.isoformat() for d in data],
        "CMP": [float(d.CMP) for d in data],
        "DMA_5": [float(d.DMA_5) for d in data],
        "DMA_21": [float(d.DMA_21) for d in data],
        "DMA_60": [float(d.DMA_60) for d in data],
        "DMA_245": [float(d.DMA_245) for d in data],
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
def get_all_data(
    limit: int = 1000,
    offset: int = 0,
    db: Session = Depends(get_db)
):
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
from fastapi import Query

@router.delete("/delete")
def delete_by_trn_date(trn_date: str = Query(..., description="Date of the upload to delete"), db: Session = Depends(get_db)):
    """
    Delete all PriceMoving records for a specific TRN_DATE (YYYY-MM-DD)
    """
    try:
        date_obj = datetime.strptime(trn_date, "%Y-%m-%d").date()
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid date format. Use YYYY-MM-DD")

    # Check if data exists
    existing = db.query(PriceMoving).filter(PriceMoving.TRN_DATE == date_obj).all()
    if not existing:
        raise HTTPException(status_code=404, detail="No records found for this date")

    # Delete records
    deleted_count = db.query(PriceMoving).filter(PriceMoving.TRN_DATE == date_obj).delete(synchronize_session=False)
    db.commit()

    return {
        "message": f"Deleted {deleted_count} records for TRN_DATE {trn_date}"
    }