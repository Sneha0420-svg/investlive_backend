import io
from datetime import date
import uuid

import pandas as pd
from fastapi import APIRouter, UploadFile, File, Form, HTTPException, Depends
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy import desc
from app.database import SessionLocal
from app.models.marketpulse import (
    StockPulseTable, StockPulseTableUpload,
    StockPulseIndex, StockPulseIndexUpload
)
from app.s3_utils import upload_file_to_s3, delete_file_from_s3, get_s3_file_url

router = APIRouter(prefix="/marketpulse", tags=["marketpulse"])

# ---------------- CSV column order ----------------
STOCKPULSETABLE_COLUMNS = [
    "TYPE", "MCAP", "DMA_5", "DMA_21", "DMA_60", "DMA_245",
    "WK52H_MCAP", "WK52HDT", "WK52L_MCAP", "WK52LDT",
    "VOL", "DVMA_5", "DVMA_21", "DVMA_60", "DVMA_245",
    "WK52H_VOL", "WK52HVDT", "WK52L_VOL", "WK52LVDT"
]

STOCKPULSEINDEX_COLUMNS = [
    "ID", "TYPE", "TRN_DATE", "MCAP", "FFLT",
    "DMA_5", "DMA_21", "DMA_60", "DMA_245",
    "STOCKS", "ADV", "DEC", "UNCHG", "VOL"
]

NUMERIC_COLUMNS = [
    "MCAP", "FFLT", "DMA_5", "DMA_21", "DMA_60", "DMA_245",
    "STOCKS", "ADV", "DEC", "UNCHG", "VOL",
    "WK52H_MCAP", "WK52L_MCAP", "WK52H_VOL", "WK52L_VOL",
    "DVMA_5", "DVMA_21", "DVMA_60", "DVMA_245"
]

TABLE_MAP = {
    "stockpulse_tbl": (StockPulseTable, StockPulseTableUpload),
    "stockpulse_index": (StockPulseIndex, StockPulseIndexUpload),
}

COLUMN_MAP = {
    "stockpulse_tbl": STOCKPULSETABLE_COLUMNS,
    "stockpulse_index": STOCKPULSEINDEX_COLUMNS,
}

# ---------------- DB Dependency ----------------
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# ---------------- CSV Reader ----------------
def read_csv_safe(file_stream, expected_columns=None):
    file_stream.seek(0)
    contents = file_stream.read()
    if not contents or len(contents.strip()) == 0:
        raise HTTPException(status_code=404, detail="CSV file is empty or missing")

    file_stream.seek(0)
    try:
        df = pd.read_csv(file_stream, header=None, encoding="utf-8")
    except UnicodeDecodeError:
        file_stream.seek(0)
        df = pd.read_csv(file_stream, header=None, encoding="latin1")
    except pd.errors.EmptyDataError:
        raise HTTPException(status_code=404, detail="CSV file contains no data")

    df = df.where(pd.notnull(df), None)

    if expected_columns:
        if len(df.columns) > len(expected_columns):
            extra = len(df.columns) - len(expected_columns)
            df.columns = expected_columns + [f"extra_{i}" for i in range(extra)]
        elif len(df.columns) < len(expected_columns):
            missing = len(expected_columns) - len(df.columns)
            df.columns = df.columns.tolist() + [f"col_{i}" for i in range(missing)]
        else:
            df.columns = expected_columns

    return df

# ---------------- Upload API ----------------
@router.post("/upload/")
async def upload_file(
    mrk_date: date = Form(...),
    data_type: str = Form(...),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    data_type = data_type.lower()

    if data_type not in TABLE_MAP:
        raise HTTPException(status_code=400, detail="Invalid data_type")

    if not file.filename.lower().endswith(".csv"):
        raise HTTPException(status_code=400, detail="Only CSV files allowed")

    Model, UploadModel = TABLE_MAP[data_type]
    expected_columns = COLUMN_MAP[data_type]

    contents = await file.read()
    if not contents:
        raise HTTPException(status_code=400, detail="Uploaded file is empty")

    file_like = io.BytesIO(contents)
    df = read_csv_safe(file_like, expected_columns)
    file_like.seek(0)

    # Upload CSV to S3
    try:
        s3_key = upload_file_to_s3(
            file_obj=file_like,
            folder=f"heatmap/{data_type}",
            filename=file.filename
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"S3 upload failed: {e}")

    # Save upload record (keep history)
    upload_entry = UploadModel(
        mrk_date=mrk_date,
        data_type=data_type,
        file_name=file.filename,
        file_path=s3_key,
    )

    # Prepare database objects for main table
    model_columns = set(Model.__table__.columns.keys())
    objects = []

    for _, row in df.iterrows():
        record = {}
        for col in expected_columns:
            if col in model_columns and col != "ID":
                val = row[col]
                if col in NUMERIC_COLUMNS:
                    try:
                        val = int(float(val)) if val not in (None, "") else 0
                    except ValueError:
                        val = 0
                record[col] = val
        objects.append(Model(**record))

    if not objects:
        delete_file_from_s3(s3_key)
        raise HTTPException(status_code=400, detail="No valid rows found in CSV")

    # Insert into DB
    try:
        # 1️⃣ Delete existing data for this table
        db.query(Model).delete()
        db.flush()

        # 2️⃣ Add new data
        db.bulk_save_objects(objects)

        # 3️⃣ Save upload record
        db.add(upload_entry)
        db.commit()
    except SQLAlchemyError as e:
        db.rollback()
        delete_file_from_s3(s3_key)
        raise HTTPException(status_code=500, detail=f"Database insert failed: {e}")

    db.refresh(upload_entry)

    return {
        "status": "success",
        "data_type": data_type,
        "file": file.filename,
        "s3_key": s3_key,
        "rows_inserted": len(objects),
        "file_url": get_s3_file_url(s3_key)
    }
    
# ---------------- Get All Uploads ----------------
@router.get("/uploads/")
def get_all_uploads(data_type: str, db: Session = Depends(get_db)):
    data_type = data_type.lower()
    if data_type not in ["stockpulse_tbl", "stockpulse_index"]:
        raise HTTPException(status_code=400, detail="Invalid data_type")

    UploadModel = StockPulseTableUpload if data_type == "stockpulse_tbl" else StockPulseIndexUpload

    uploads = db.query(UploadModel).order_by(UploadModel.mrk_date.desc()).all()
    result = []
    for u in uploads:
        result.append({
            "id": u.id,
            "file_name": u.file_name,
            "mrk_date": u.mrk_date,
            "data_type": u.data_type,
            "file_path": u.file_path,
            "file_url": get_s3_file_url(u.file_path)
        })

    return {"status": "success", "data_type": data_type, "uploads": result}

# ---------------- Get All Data Route ----------------
@router.get("/all_data/")
def get_all_data(data_type: str, db: Session = Depends(get_db)):
    """
    Fetch all rows from the specified table.
    data_type: "stockpulse_tbl" or "stockpulse_index"
    """
    data_type = data_type.lower()
    
    if data_type == "stockpulse_tbl":
        Model = StockPulseTable
    elif data_type == "stockpulse_index":
        Model = StockPulseIndex
    else:
        raise HTTPException(status_code=400, detail="Invalid data_type")
    
    rows = db.query(Model).all()
    if not rows:
        raise HTTPException(status_code=404, detail="No data found in table")

    result = [row.__dict__ for row in rows]
    for r in result:
        r.pop("_sa_instance_state", None)  # Remove SQLAlchemy internal state

    return {
        "status": "success",
        "data_type": data_type,
        "rows": len(result),
        "data": result
    }
@router.delete("/upload/{upload_id}/")
def delete_upload(upload_id: int, data_type: str, db: Session = Depends(get_db)):
    data_type = data_type.lower()
    if data_type not in ["stockpulse_tbl", "stockpulse_index"]:
        raise HTTPException(status_code=400, detail="Invalid data_type")

    UploadModel = StockPulseTableUpload if data_type == "stockpulse_tbl" else StockPulseIndexUpload

    upload_entry = db.query(UploadModel).filter(UploadModel.id == upload_id).first()
    if not upload_entry:
        raise HTTPException(status_code=404, detail="Upload not found")

    # Delete the file from S3
    try:
        delete_file_from_s3(upload_entry.file_path)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to delete file from S3: {e}")

    # Delete the record from DB
    try:
        db.delete(upload_entry)
        db.commit()
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to delete upload record: {e}")

    return {"status": "success", "message": f"Upload {upload_id} deleted successfully"}