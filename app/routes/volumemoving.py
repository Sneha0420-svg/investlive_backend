# app/routes/volumemoving.py

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from sqlalchemy.orm import Session
from datetime import date, timedelta, datetime
import csv
from sqlalchemy import func
from app.models.volumemoving import VolumeMoving
from app.database import SessionLocal

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
# Upload CSV (Auto delimiter + auto date format)
# ----------------------
@router.post("/upload")
def upload_csv(file: UploadFile = File(...), db: Session = Depends(get_db)):

    if not file.filename.endswith(".csv"):
        raise HTTPException(status_code=400, detail="Only CSV files are allowed")

    try:
        content = file.file.read().decode("utf-8-sig").splitlines()

        if not content:
            raise HTTPException(status_code=400, detail="CSV file is empty")

        # ✅ Auto detect delimiter (TAB or comma)
        first_line = content[0]
        delimiter = "\t" if "\t" in first_line else ","

        reader = csv.reader(content, delimiter=delimiter, skipinitialspace=True)

        records_added = 0
        records_updated = 0
        errors = 0

        for row in reader:
            if not row or len(row) < 6:
                continue

            try:
                sccode = row[0].strip()
                scrip = row[1].strip()
                cocode = row[2].strip()
                isin = row[3].strip()
                curvol = int(row[4].strip())

                # ✅ Auto handle both date formats
                date_str = row[5].strip()
                try:
                    trn_date = datetime.strptime(date_str, "%d-%m-%Y").date()
                except ValueError:
                    trn_date = datetime.strptime(date_str, "%Y-%m-%d").date()

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
            "records_inserted": records_added,
            "records_updated": records_updated,
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
def get_all_data(
    limit: int = 1000,
    offset: int = 0,
    db: Session = Depends(get_db)
):

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
# Delete VolumeMoving records for a specific TRN_DATE
# ----------------------
from fastapi import Query

@router.delete("/delete")
def delete_by_trn_date(
    trn_date: str = Query(..., description="Date of the upload to delete in YYYY-MM-DD format"),
    db: Session = Depends(get_db)
):
    """
    Delete all VolumeMoving records for a specific TRN_DATE
    """
    try:
        date_obj = datetime.strptime(trn_date, "%Y-%m-%d").date()
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid date format. Use YYYY-MM-DD")

    # Check if any records exist
    existing = db.query(VolumeMoving).filter(VolumeMoving.TRN_DATE == date_obj).all()
    if not existing:
        raise HTTPException(status_code=404, detail="No records found for this date")

    # Delete records
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
    """
    Return all upload dates (TRN_DATE) with total records for each date
    """
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