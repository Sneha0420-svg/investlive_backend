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
    data_date: str = Form(...),
    data_type: str = Form(...),
    files: List[UploadFile] = File(...),
    db: Session = Depends(get_db),
):
    data_type = data_type.lower()
    if data_type not in TABLE_MAP:
        raise HTTPException(status_code=400, detail="Invalid data_type")

    Model, UploadModel, expected_columns = TABLE_MAP[data_type]

    all_dfs = []
    s3_keys = []

    try:
        # ---------- Process each file ----------
        for file in files:
            if not file.filename.lower().endswith(".csv"):
                raise HTTPException(status_code=400, detail=f"{file.filename} is not a CSV")

            content = await file.read()
            file_like = io.BytesIO(content)

            # Upload to S3
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
            df["EX_DT"] = df["EX_DT"].apply(parse_date_safe)

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
            raise HTTPException(
                status_code=400,
                detail={"message": "Errors in CSV", "sample": errors[:10]}
            )

        if not objects:
            raise HTTPException(status_code=400, detail="No valid rows found")

        # 🔥🔥🔥 IMPORTANT CHANGE HERE 🔥🔥🔥
        # ---------- DELETE ALL OLD DATA ----------
        db.query(Model).delete(synchronize_session=False)

        # ---------- Save metadata ----------
        upload_entry = UploadModel(
            group_id=str(uuid.uuid4()),
            data_date=datetime.strptime(data_date, "%Y-%m-%d").date(),
            data_type=data_type,
            file_name=",".join([f.filename for f in files]),
            file_path=",".join(s3_keys)
        )

        # ---------- DB Insert ----------
        db.add(upload_entry)
        db.bulk_save_objects(objects)

        db.commit()

        return {
            "status": "success",
            "files_uploaded": [f.filename for f in files],
            "rows_inserted": len(objects),
            "s3_keys": s3_keys
        }

    except Exception as e:
        db.rollback()

        # Cleanup S3 if failure
        for key in s3_keys:
            delete_file_from_s3(key)

        raise HTTPException(status_code=500, detail=str(e))
# ---------------- Get all uploads ----------------
@router.get("/{data_type}/", response_model=List[UploadBase])
def get_all_uploads(data_type: str, db: Session = Depends(get_db)):
    data_type = data_type.lower()
    if data_type not in UPLOAD_TABLES:
        raise HTTPException(status_code=400, detail="Invalid data_type")

    UploadModel = UPLOAD_TABLES[data_type]
    return db.query(UploadModel).order_by(UploadModel.data_date.desc()).all()

@router.get("/{data_type}/latest-data-file/")
def get_latest_upload_file(data_type: str, db: Session = Depends(get_db)):

    data_type = data_type.lower()

    if data_type not in TABLE_MAP:
        raise HTTPException(status_code=400, detail="Invalid data_type")

    Model, _, _ = TABLE_MAP[data_type]


    result = (
        db.query(Model)
        .all()
    )

    return result

@router.get("/{data_type}/latest-data-file/{isin}")
def get_latest_upload_by_isin(data_type: str, isin: str, db: Session = Depends(get_db)):

    data_type = data_type.lower()

    if data_type not in TABLE_MAP:
        raise HTTPException(status_code=400, detail="Invalid data_type")

    Model, _, _ = TABLE_MAP[data_type]

    result = (
        db.query(Model)
        .filter(Model.ISIN == isin.strip())
        .all()
    )

    if not result:
        raise HTTPException(status_code=404, detail="No records found for this ISIN")

    return result
@router.get("/{data_type}/files/{upload_id}")
def download_combined_csv(
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

    # 🔥 Split multiple S3 keys
    file_keys = upload.file_path.split(",")

    dfs = []

    try:
        for key in file_keys:
            file_stream = get_file_stream_from_s3(key.strip())

            df = pd.read_csv(file_stream, header=None)
            dfs.append(df)

        # Merge all CSVs
        final_df = pd.concat(dfs, ignore_index=True)

        # Convert to CSV
        stream = io.StringIO()
        final_df.to_csv(stream, index=False)
        stream.seek(0)

        return StreamingResponse(
            iter([stream.getvalue()]),
            media_type="text/csv",
            headers={
                "Content-Disposition": f"attachment; filename={data_type}.csv"
            },
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
# ---------------- Update upload ----------------
@router.put("/{data_type}/{upload_id}/")
async def update_upload(
    data_type: str,
    upload_id: int,
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