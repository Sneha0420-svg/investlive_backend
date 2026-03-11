# app/routes/volumemoving.py

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Query
from sqlalchemy.orm import Session
from datetime import date, timedelta, datetime
import csv
from sqlalchemy import func
from app.models.volumemoving import VolumeMoving
from app.database import SessionLocal
from app.s3_utils import upload_file_to_s3, delete_file_from_s3, get_file_stream_from_s3
import io
router = APIRouter(prefix="/volumemoving", tags=["VolumeMoving"])


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
# Helper: Safe strip
# ----------------------
def safe_strip(val):
    if val is None:
        return None
    return str(val).strip()


# ----------------------
# Upload CSV to S3
# ----------------------
@router.post("/upload")
def upload_csv(file: UploadFile = File(...), db: Session = Depends(get_db)):

    if not file.filename.endswith(".csv"):
        raise HTTPException(status_code=400, detail="Only CSV files are allowed")

    try:
        # ----------------------
        # Read file into memory
        # ----------------------
        content_bytes = file.file.read()  # read once
        if not content_bytes:
            raise HTTPException(status_code=400, detail="CSV file is empty")

        # ----------------------
        # Upload to S3
        # ----------------------
        s3_key = upload_file_to_s3(io.BytesIO(content_bytes), f"volumemoving/{datetime.today().strftime('%Y%m%d')}_{file.filename}")

        # ----------------------
        # Parse CSV from memory
        # ----------------------
        content_str = content_bytes.decode("utf-8-sig").splitlines()
        first_line = content_str[0]
        delimiter = "\t" if "\t" in first_line else ","
        reader = csv.reader(content_str, delimiter=delimiter, skipinitialspace=True)

        records_added = 0
        records_updated = 0
        errors = 0

        for row in reader:
            if not row or len(row) < 6:
                continue

            try:
                # Safely convert values to strings
                sccode = str(row[0]).strip() if row[0] is not None else None
                scrip = str(row[1]).strip() if row[1] is not None else None
                cocode = str(row[2]).strip() if row[2] is not None else None
                isin = str(row[3]).strip() if row[3] is not None else None

                # Handle CURVOL safely (might be float or int)
                curvol = int(float(row[4])) if row[4] not in (None, "") else None

                # Auto parse date formats
                date_str = str(row[5]).strip()
                try:
                    trn_date = datetime.strptime(date_str, "%d-%m-%Y").date()
                except ValueError:
                    trn_date = datetime.strptime(date_str, "%Y-%m-%d").date()

                # Check if record exists
                existing = (
                    db.query(VolumeMoving)
                    .filter(VolumeMoving.ISIN == isin)
                    .filter(VolumeMoving.TRN_DATE == trn_date)
                    .first()
                )

                if existing:
                    existing.SCCODE = sccode
                    existing.SCRIP = scrip
                    existing.COCODE = cocode
                    existing.CURVOL = curvol
                    records_updated += 1
                else:
                    vm = VolumeMoving(
                        SCCODE=sccode,
                        SCRIP=scrip,
                        COCODE=cocode,
                        ISIN=isin,
                        CURVOL=curvol,
                        TRN_DATE=trn_date
                    )
                    db.add(vm)
                    records_added += 1

            except Exception as e:
                print("Row Error:", row, "->", e)
                errors += 1
                continue

        db.commit()

        return {
            "message": "Upload completed",
            "s3_key": s3_key,
            "records_inserted": records_added,
            "records_updated": records_updated,
            "errors": errors
        }

    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))

# ----------------------
# Get Last 2 Years Volume Data by ISIN
# ----------------------
@router.get("/graph/isin/{isin}")
def get_graph_data_by_isin(isin: str, db: Session = Depends(get_db)):

    two_years_ago = date.today() - timedelta(days=730)

    data = (
        db.query(VolumeMoving)
        .filter(VolumeMoving.ISIN == isin)
        .filter(VolumeMoving.TRN_DATE >= two_years_ago)
        .order_by(VolumeMoving.TRN_DATE)
        .all()
    )

    if not data:
        raise HTTPException(status_code=404, detail="Data not found for this ISIN")

    return {
        "dates": [d.TRN_DATE.isoformat() for d in data],
        "CURVOL": [int(d.CURVOL) for d in data],
    }


# ----------------------
# Get All Data (Pagination)
# ----------------------
@router.get("/all")
def get_all_data(limit: int = 1000, offset: int = 0, db: Session = Depends(get_db)):

    data = (
        db.query(VolumeMoving)
        .order_by(VolumeMoving.TRN_DATE.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )

    return [
        {
            "ID": d.ID,
            "SCCODE": d.SCCODE,
            "SCRIP": d.SCRIP,
            "COCODE": d.COCODE,
            "ISIN": d.ISIN,
            "CURVOL": int(d.CURVOL) if d.CURVOL else None,
            "TRN_DATE": d.TRN_DATE.isoformat() if d.TRN_DATE else None,
        }
        for d in data
    ]


# ----------------------
# Get All SCCODEs
# ----------------------
@router.get("/sccodes")
def get_sccodes(db: Session = Depends(get_db)):
    sccodes = db.query(VolumeMoving.SCCODE, VolumeMoving.SCRIP).distinct().all()
    return [{"SCCODE": s[0], "SCRIP": s[1]} for s in sccodes]


# ----------------------
# Delete VolumeMoving records by TRN_DATE
# ----------------------
@router.delete("/delete")
def delete_by_trn_date(
    trn_date: str = Query(..., description="Date of the upload to delete in YYYY-MM-DD format"),
    db: Session = Depends(get_db)
):
    try:
        date_obj = datetime.strptime(trn_date, "%Y-%m-%d").date()
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid date format. Use YYYY-MM-DD")

    existing = db.query(VolumeMoving).filter(VolumeMoving.TRN_DATE == date_obj).all()
    if not existing:
        raise HTTPException(status_code=404, detail="No records found for this date")

    deleted_count = db.query(VolumeMoving).filter(VolumeMoving.TRN_DATE == date_obj).delete(synchronize_session=False)
    db.commit()

    return {
        "message": f"Deleted {deleted_count} records for TRN_DATE {trn_date}"
    }


# ----------------------
# Get all upload dates with total records
# ----------------------
@router.get("/uploads")
def get_all_uploads(db: Session = Depends(get_db)):
    uploads = (
        db.query(
            VolumeMoving.TRN_DATE,
            func.count(VolumeMoving.ID).label("TOTAL_RECORDS")
        )
        .group_by(VolumeMoving.TRN_DATE)
        .order_by(VolumeMoving.TRN_DATE.desc())
        .all()
    )

    return [
        {"TRN_DATE": u.TRN_DATE.isoformat(), "TOTAL_RECORDS": u.TOTAL_RECORDS}
        for u in uploads
    ]