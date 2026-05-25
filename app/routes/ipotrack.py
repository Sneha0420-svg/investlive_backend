# /routes/ipotrack.py

import io
from datetime import date
from uuid import uuid4

from fastapi import APIRouter, UploadFile, File, Form, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
import pandas as pd

from app.database import SessionLocal
from app.models.ipotrack import IpoTrack,IpoTrackUpload
from app.s3_utils import upload_file_to_s3, delete_file_from_s3, get_file_stream_from_s3

router = APIRouter(prefix="/ipotrack", tags=["IPO Track"])


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


def to_decimal(val):
    if pd.isna(val) or val == "":
        return None
    try:
        return float(val)
    except Exception:
        return None


def generate_s3_key(filename: str):
    return f"ipotrack/{uuid4()}_{filename}"


# -------------------- UPLOAD --------------------
@router.post("/upload")
async def upload_ipotrack(
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
        "ID","INDIC","COCODE","CO_NAME","ISS_OPEN","ISS_CLOSE",
        "HIGH","LOW","IPO_PR","FV","ISS_AMT","ISS_QTY",
        "LISTED_PR","LISTED_GAIN","LISTED_DT","CMP","CUR_GAIN",
        "MIN_LOT","EXCH","ISS_TYPE",
        "LM1","LM2","LM3","LM4","LM5","LM6","LM7","LM8","LM9","LM10",
        "LM11","LM12","LM13","LM14","LM15",
        "MKTMKR1","MKTMKR2","MKTMKR3"
    ]

    if df.shape[1] != len(headers):
        raise HTTPException(400, f"File must have exactly {len(headers)} columns")

    df.columns = headers

    # ⚠️ deletes all existing records (same as your pattern)
    db.query(IpoTrack).delete()
    db.commit()

    records = []
    skipped_rows = 0

    for _, row in df.iterrows():
        try:
            if not row["CO_NAME"]:
                skipped_rows += 1
                continue

            record = IpoTrack(
                ID=int(row["ID"]) if not pd.isna(row["ID"]) else None,
                INDIC=safe_strip(row["INDIC"]),
                COCODE=safe_strip(row["COCODE"]),
                CO_NAME=safe_strip(row["CO_NAME"]),

                ISS_OPEN=parse_date(row["ISS_OPEN"]),
                ISS_CLOSE=parse_date(row["ISS_CLOSE"]),

                HIGH=to_decimal(row["HIGH"]),
                LOW=to_decimal(row["LOW"]),
                IPO_PR=to_decimal(row["IPO_PR"]),
                FV=to_decimal(row["FV"]),

                ISS_AMT=to_decimal(row["ISS_AMT"]),
                ISS_QTY=to_decimal(row["ISS_QTY"]),

                LISTED_PR=to_decimal(row["LISTED_PR"]),
                LISTED_GAIN=to_decimal(row["LISTED_GAIN"]),
                LISTED_DT=parse_date(row["LISTED_DT"]),

                CMP=to_decimal(row["CMP"]),
                CUR_GAIN=to_decimal(row["CUR_GAIN"]),

                MIN_LOT=int(row["MIN_LOT"]) if not pd.isna(row["MIN_LOT"]) else None,

                EXCH=safe_strip(row["EXCH"]),
                ISS_TYPE=safe_strip(row["ISS_TYPE"]),

                LM1=safe_strip(row["LM1"]),
                LM2=safe_strip(row["LM2"]),
                LM3=safe_strip(row["LM3"]),
                LM4=safe_strip(row["LM4"]),
                LM5=safe_strip(row["LM5"]),
                LM6=safe_strip(row["LM6"]),
                LM7=safe_strip(row["LM7"]),
                LM8=safe_strip(row["LM8"]),
                LM9=safe_strip(row["LM9"]),
                LM10=safe_strip(row["LM10"]),
                LM11=safe_strip(row["LM11"]),
                LM12=safe_strip(row["LM12"]),
                LM13=safe_strip(row["LM13"]),
                LM14=safe_strip(row["LM14"]),
                LM15=safe_strip(row["LM15"]),

                MKTMKR1=safe_strip(row["MKTMKR1"]),
                MKTMKR2=safe_strip(row["MKTMKR2"]),
                MKTMKR3=safe_strip(row["MKTMKR3"]),
            )

            records.append(record)

        except Exception:
            skipped_rows += 1
            continue

    if records:
        db.bulk_save_objects(records)
        db.commit()

    # Save upload metadata
    upload_row = IpoTrackUpload(
        mkt_date=mkt_date,
        file_name=file.filename,
        file_path=s3_key
    )
    db.add(upload_row)
    db.commit()

    return {
        "message": "Uploaded successfully",
        "inserted_records": len(records),
        "skipped_rows": skipped_rows
    }


# -------------------- LIST --------------------
@router.get("/uploads")
def get_uploads(db: Session = Depends(get_db)):
    uploads = db.query(IpoTrackUpload).order_by(IpoTrackUpload.mkt_date.desc()).all()

    return [
        {
            "id": u.id,
            "mkt_date": u.mkt_date,
            "file_name": u.file_name,
            "download_url": f"/ipotrack/download/{u.id}"
        }
        for u in uploads
    ]


# -------------------- DOWNLOAD --------------------
@router.get("/download/{upload_id}")
def download_file(upload_id: int, db: Session = Depends(get_db)):
    upload = db.query(IpoTrackUpload).filter(IpoTrackUpload.id == upload_id).first()

    if not upload:
        raise HTTPException(404, "Upload not found")

    file_stream = get_file_stream_from_s3(upload.file_path)

    if not file_stream:
        raise HTTPException(404, "File not found in S3")

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
def delete_upload(upload_id: int, db: Session = Depends(get_db)):
    upload = db.query(IpoTrackUpload).filter(IpoTrackUpload.id == upload_id).first()

    if not upload:
        raise HTTPException(404, "Upload not found")

    db.query(IpoTrack).delete()

    if upload.file_path:
        delete_file_from_s3(upload.file_path)

    db.delete(upload)
    db.commit()

    return {"message": "Deleted successfully"}


# -------------------- GET ALL --------------------
@router.get("/all")
def get_all_ipotrack(db: Session = Depends(get_db)):
    data = db.query(IpoTrack).all()

    return [row.__dict__ for row in data]