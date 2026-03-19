import io
import uuid
from datetime import datetime
from typing import List

import pandas as pd
from fastapi import APIRouter, UploadFile, File, Form, HTTPException, Depends, Path
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError

from app.database import SessionLocal
from app.models.corpdiary import (
    Bonus, Split, Div, BonusUpload, SplitUpload, DivUpload
)
from app.schemas.heatmap import UploadBase
from app.s3_utils import upload_file_to_s3, get_file_stream_from_s3, delete_file_from_s3, get_s3_file_url

router = APIRouter(prefix="/corpdiary", tags=["corpdiary"])

# ---------------- DB Dependency ----------------
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# ---------------- CSV Columns ----------------
SPLIT_COLUMNS = ["ID", "ISIN", "OLD_FV", "NEW_FV", "EX_DT", "INDIC"]
BONUS_COLUMNS = ["ID", "ISIN", "BONUS", "PRE", "EX_DT", "INDIC"]
DIV_COLUMNS = ["ID", "ISIN", "DIV_RATE", "DIV_TYPE", "EX_DT"]

TABLE_MAP = {
    "split": (Split, SplitUpload, SPLIT_COLUMNS),
    "bonus": (Bonus, BonusUpload, BONUS_COLUMNS),
    "dividend": (Div, DivUpload, DIV_COLUMNS),
}

UPLOAD_TABLES = {
    "split": SplitUpload,
    "bonus": BonusUpload,
    "dividend": DivUpload,
}

@router.post("/upload/")
async def upload_file(
    upload_date: str = Form(...),
    data_date: str = Form(...),
    data_type: str = Form(...),
    files: List[UploadFile] = File(...),  # 🔥 multiple files
    db: Session = Depends(get_db),
):
    data_type = data_type.lower()
    if data_type not in TABLE_MAP:
        raise HTTPException(status_code=400, detail="Invalid data_type")

    Model, UploadModel, expected_columns = TABLE_MAP[data_type]

    all_dfs = []
    s3_keys = []

    # ---------- Process each file ----------
    for file in files:
        if not file.filename.lower().endswith(".csv"):
            raise HTTPException(status_code=400, detail=f"{file.filename} is not a CSV")

        content = await file.read()
        file_like = io.BytesIO(content)

        # Upload each file to S3
        s3_key = upload_file_to_s3(
            file_obj=file_like,
            folder=f"corpdiary/{data_type}",
            filename=file.filename
        )
        s3_keys.append(s3_key)

        # Read CSV
        try:
            df = pd.read_csv(io.BytesIO(content), header=None, encoding="utf-8")
        except UnicodeDecodeError:
            df = pd.read_csv(io.BytesIO(content), header=None, encoding="latin1")

        if df.shape[1] != len(expected_columns):
            raise HTTPException(
                status_code=400,
                detail=f"{file.filename}: Expected {len(expected_columns)} columns, got {df.shape[1]}",
            )

        df.columns = expected_columns
        df = df.where(pd.notnull(df), None)

        all_dfs.append(df)

    # ---------- Merge all CSVs ----------
    df = pd.concat(all_dfs, ignore_index=True)

    # ---------- DATE FIX ----------
    def parse_date_safe(x):
        if x in (None, "", "nan"):
            return None
        for fmt in ("%d-%m-%Y", "%Y-%m-%d", "%d/%m/%Y"):
            try:
                return datetime.strptime(str(x), fmt).date()
            except:
                continue
        raise ValueError(f"Invalid date format: {x}")

    if "EX_DT" in df.columns:
        try:
            df["EX_DT"] = df["EX_DT"].apply(parse_date_safe)
        except Exception as e:
            for key in s3_keys:
                delete_file_from_s3(key)
            raise HTTPException(status_code=400, detail=str(e))

    # ---------- Prepare ORM ----------
    model_columns = set(Model.__table__.columns.keys())
    objects = []
    errors = []

    for idx, row in df.iterrows():
        try:
            record = {}

            for col in expected_columns:
                if col not in model_columns or col == "ID":
                    continue

                record[col] = row[col]

            objects.append(Model(**record))

        except Exception as e:
            errors.append({"row": int(idx), "error": str(e)})

    if errors:
        for key in s3_keys:
            delete_file_from_s3(key)
        raise HTTPException(
            status_code=400,
            detail={"message": "Errors in CSV", "sample": errors[:10]}
        )

    if not objects:
        raise HTTPException(status_code=400, detail="No valid rows found")

    # ---------- Save metadata ----------
    upload_entry = UploadModel(
        group_id=str(uuid.uuid4()),
        upload_date=datetime.strptime(upload_date, "%Y-%m-%d").date(),
        data_date=datetime.strptime(data_date, "%Y-%m-%d").date(),
        data_type=data_type,
        file_name=",".join([f.filename for f in files]),  # store all names
        file_path=",".join(s3_keys)  # store multiple paths
    )

    # ---------- DB Insert ----------
    try:
        db.add(upload_entry)
        db.bulk_save_objects(objects)
        db.commit()
    except Exception as e:
        db.rollback()
        for key in s3_keys:
            delete_file_from_s3(key)
        raise HTTPException(status_code=500, detail=str(e))

    return {
        "status": "success",
        "files_uploaded": [f.filename for f in files],
        "rows_inserted": len(objects),
        "s3_keys": s3_keys
    }
# ---------------- Get all uploads ----------------
@router.get("/{data_type}/", response_model=List[UploadBase])
def get_all_uploads(data_type: str, db: Session = Depends(get_db)):
    data_type = data_type.lower()
    if data_type not in UPLOAD_TABLES:
        raise HTTPException(status_code=400, detail="Invalid data_type")

    UploadModel = UPLOAD_TABLES[data_type]
    return db.query(UploadModel).order_by(UploadModel.upload_date.desc()).all()

# ---------------- Latest upload (full file) ----------------
@router.get("/{data_type}/latest-data-file/")
def get_latest_upload_file(data_type: str, db: Session = Depends(get_db)):
    data_type = data_type.lower()
    if data_type not in TABLE_MAP:
        raise HTTPException(status_code=400, detail="Invalid data_type")

    _, UploadModel, expected_columns = TABLE_MAP[data_type]

    latest = db.query(UploadModel).order_by(UploadModel.data_date.desc()).first()
    if not latest:
        raise HTTPException(status_code=404, detail="No uploads found")

    file_stream = get_file_stream_from_s3(latest.file_path)
    if not file_stream:
        raise HTTPException(status_code=404, detail="File not found on S3")

    df = pd.read_csv(file_stream, header=None)
    df.columns = expected_columns
    df = df.where(pd.notnull(df), None)
    return df.to_dict(orient="records")

# ---------------- Latest upload filtered by ISIN ----------------
@router.get("/{data_type}/latest-data-file/{isin}")
def get_latest_upload_by_isin(data_type: str, isin: str, db: Session = Depends(get_db)):
    data_type = data_type.lower()
    if data_type not in TABLE_MAP:
        raise HTTPException(status_code=400, detail="Invalid data_type")

    _, UploadModel, expected_columns = TABLE_MAP[data_type]

    latest = db.query(UploadModel).order_by(UploadModel.data_date.desc()).first()
    if not latest:
        raise HTTPException(status_code=404, detail="No uploads found")

    file_stream = get_file_stream_from_s3(latest.file_path)
    if not file_stream:
        raise HTTPException(status_code=404, detail="File not found on S3")

    df = pd.read_csv(file_stream, header=None)
    df.columns = expected_columns
    df = df.where(pd.notnull(df), None)

    df["ISIN"] = df["ISIN"].astype(str).str.strip()
    isin = isin.strip()
    filtered = df[df["ISIN"] == isin]

    if filtered.empty:
        raise HTTPException(status_code=404, detail="No records found for this ISIN")

    return filtered.to_dict(orient="records")

# ---------------- Download file from S3 ----------------
@router.get("/{data_type}/files/{upload_id}")
def download_file_presigned(
    data_type: str,
    upload_id: int,
    db: Session = Depends(get_db),
):
    data_type = data_type.lower()
    if data_type not in UPLOAD_TABLES:
        raise HTTPException(status_code=400, detail="Invalid data_type")

    UploadModel = UPLOAD_TABLES[data_type]
    upload = db.query(UploadModel).filter(UploadModel.id == upload_id).first()
    if not upload:
        raise HTTPException(status_code=404, detail="Upload not found")

    if not upload.file_path:
        raise HTTPException(status_code=404, detail="File path not set")

    # ✅ Use presigned URL instead of streaming
    presigned_url = get_s3_file_url(upload.file_path)
    if not presigned_url:
        raise HTTPException(status_code=404, detail="File not found on S3")

    return {
        "file_name": upload.file_name,
        "url": presigned_url
    }
# ---------------- Update upload ----------------
@router.put("/{data_type}/{upload_id}/")
async def update_upload(
    data_type: str,
    upload_id: int,
    upload_date: str = Form(None),
    data_date: str = Form(None),
    new_data_type: str = Form(None),
    file: UploadFile = File(None),
    db: Session = Depends(get_db),
):
    data_type = data_type.lower()
    if data_type not in UPLOAD_TABLES:
        raise HTTPException(status_code=400, detail="Invalid data_type")

    UploadModel = UPLOAD_TABLES[data_type]
    upload = db.query(UploadModel).filter(UploadModel.id == upload_id).first()
    if not upload:
        raise HTTPException(status_code=404, detail="Upload not found")

    # Update dates
    if upload_date:
        upload.upload_date = datetime.strptime(upload_date, "%Y-%m-%d").date()
    if data_date:
        upload.data_date = datetime.strptime(data_date, "%Y-%m-%d").date()

    # Update type
    if new_data_type:
        new_data_type = new_data_type.lower()
        if new_data_type not in UPLOAD_TABLES:
            raise HTTPException(status_code=400, detail="Invalid new_data_type")
        upload.data_type = new_data_type

    # Update file
    if file:
        if not file.filename.lower().endswith(".csv"):
            raise HTTPException(status_code=400, detail="Only CSV files allowed")

        # Upload new file to S3
        new_s3_key = upload_file_to_s3(file, f"corpdiary/{data_type}")

        # Delete old S3 file
        if upload.file_path:
            delete_file_from_s3(upload.file_path)

        upload.file_name = file.filename
        upload.file_path = new_s3_key

    db.commit()
    db.refresh(upload)
    return {
        "id": upload.id,
        "upload_date": str(upload.upload_date),
        "data_date": str(upload.data_date),
        "data_type": upload.data_type,
        "file_name": upload.file_name,
        "file_path": upload.file_path,
    }

# ---------------- Delete upload ----------------
@router.delete("/{data_type}/{upload_id}/")
def delete_upload(data_type: str, upload_id: int, db: Session = Depends(get_db)):
    data_type = data_type.lower()
    if data_type not in UPLOAD_TABLES:
        raise HTTPException(status_code=400, detail="Invalid data_type")

    UploadModel = UPLOAD_TABLES[data_type]
    upload = db.query(UploadModel).filter(UploadModel.id == upload_id).first()
    if not upload:
        raise HTTPException(status_code=404, detail="Upload not found")

    # Delete file from S3
    if upload.file_path:
        delete_file_from_s3(upload.file_path)

    db.delete(upload)
    db.commit()

    return {"status": "deleted", "id": upload_id}