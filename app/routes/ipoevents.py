import io
from datetime import date
from uuid import uuid4

from fastapi import APIRouter, UploadFile, File, Form, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
import pandas as pd

from app.database import SessionLocal
from app.models.ipoevents import IPOEvents, IPOEventsUpload
from app.s3_utils import upload_file_to_s3, delete_file_from_s3, get_file_stream_from_s3

router = APIRouter(prefix="/ipoevents", tags=["IPO Events"])

# -------------------- DB DEP --------------------
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# -------------------- HELPERS --------------------
def safe_strip(val):
    return None if val is None or pd.isna(val) else str(val).strip()


def parse_date(val):
    if pd.isna(val) or val == "":
        return None
    if isinstance(val, pd.Timestamp):
        return val.date()
    try:
        return pd.to_datetime(val).date()
    except Exception:
        return None


def generate_s3_key(filename: str):
    return f"ipoevents/{uuid4()}_{filename}"


# -------------------- UPLOAD --------------------
@router.post("/upload")
async def upload_ipoevents(
    mkt_date: date = Form(...),
    file: UploadFile = File(...),
    db: Session = Depends(get_db)
):
    file_bytes = await file.read()

    # Upload to S3
    try:
        s3_key = upload_file_to_s3(io.BytesIO(file_bytes), generate_s3_key(file.filename))
    except Exception as e:
        raise HTTPException(500, f"S3 upload failed: {str(e)}")

    # Read file
    try:
        df = pd.read_excel(io.BytesIO(file_bytes), header=None)
    except Exception:
        try:
            df = pd.read_csv(io.StringIO(file_bytes.decode("utf-8")), header=None)
        except Exception:
            raise HTTPException(400, "Invalid file format (only Excel/CSV supported)")

    headers = [
        "SCRIP", "ISS_OPEN", "SHEDULE_CLOSE", "LATE_CLOSE", "ALLOTMENT", "REFUND",
        "DEMAT", "TRADING", "DP_DATE", "FP_DATE",
        "DRHP_DATE", "RHP_DATE", "PROS_DATE", "ID"
    ]

    if df.shape[1] != len(headers):
        raise HTTPException(400, f"File must have exactly {len(headers)} columns")

    df.columns = headers

    # Optional: delete old data (⚠️ careful in production)
    db.query(IPOEvents).delete()
    db.commit()

    # Insert records
    records = []
    skipped_rows = 0

    for idx, row in df.iterrows():
        try:
            if not row["SCRIP"]:
                skipped_rows += 1
                continue

            record = IPOEvents(
                SCRIP=safe_strip(row["SCRIP"]),
                ISS_OPEN=parse_date(row["ISS_OPEN"]),
                SHEDULE_CLOSE=parse_date(row["SHEDULE_CLOSE"]),
                LATE_CLOSE=parse_date(row["LATE_CLOSE"]),
                ALLOTMENT=parse_date(row["ALLOTMENT"]),
                REFUND=parse_date(row["REFUND"]),
                DEMAT=parse_date(row["DEMAT"]),
                TRADING=parse_date(row["TRADING"]),
                DP_DATE=parse_date(row["DP_DATE"]),
                FP_DATE=parse_date(row["FP_DATE"]),
                DRHP_DATE=parse_date(row["DRHP_DATE"]),
                RHP_DATE=parse_date(row["RHP_DATE"]),
                PROS_DATE=parse_date(row["PROS_DATE"]),
                ID=int(row["ID"]) 
            )

            records.append(record)

        except Exception as e:
            skipped_rows += 1
            continue

    if records:
        db.bulk_save_objects(records)
        db.commit()

    # Save upload metadata
    try:
        upload_row = IPOEventsUpload(
            mkt_date=mkt_date,
            file_name=file.filename,
            file_path=s3_key
        )
        db.add(upload_row)
        db.commit()
    except Exception as e:
        raise HTTPException(500, f"Upload metadata save failed: {str(e)}")

    return {
        "message": "Uploaded successfully",
        "inserted_records": len(records),
        "skipped_rows": skipped_rows
    }


# -------------------- LIST --------------------
@router.get("/uploads")
def get_ipoevents_uploads(db: Session = Depends(get_db)):
    uploads = db.query(IPOEventsUpload).order_by(IPOEventsUpload.mkt_date.desc()).all()

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
def download_ipoevents_file(upload_id: int, db: Session = Depends(get_db)):
    upload = db.query(IPOEventsUpload).filter(IPOEventsUpload.id == upload_id).first()

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
def delete_ipoevents_upload(upload_id: int, db: Session = Depends(get_db)):
    upload = db.query(IPOEventsUpload).filter(IPOEventsUpload.id == upload_id).first()

    if not upload:
        raise HTTPException(404, "Upload not found")

    # ✅ delete stock data using mkt_date
    db.query(IPOEvents).delete(synchronize_session=False)

    # ✅ delete file from S3
    if upload.file_path:
        delete_file_from_s3(upload.file_path)

    # ✅ delete upload record
    db.delete(upload)
    db.commit()

    return {"message": "Deleted successfully"}

# -------------------- GET ALL STOCKS --------------------
@router.get("/events")
def get_all_events(db: Session = Depends(get_db)):
    events = db.query(IPOEvents).order_by(IPOEvents.ID).all()
    return [
    {
        "SCRIP": e.SCRIP,
        "ISS_OPEN": e.ISS_OPEN,
        "SHEDULE_CLOSE": e.SHEDULE_CLOSE,
        "LATE_CLOSE": e.LATE_CLOSE,
        "ALLOTMENT": e.ALLOTMENT,
        "REFUND": e.REFUND,
        "DEMAT": e.DEMAT,
        "TRADING": e.TRADING,
        "DP_DATE": e.DP_DATE,
        "FP_DATE": e.FP_DATE,
        "DRHP_DATE": e.DRHP_DATE,
        "RHP_DATE": e.RHP_DATE,
        "PROS_DATE": e.PROS_DATE,
        "ID": e.ID
    }
    for e in events
]


