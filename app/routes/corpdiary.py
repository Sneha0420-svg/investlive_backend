from fastapi import APIRouter, UploadFile, File, Form, HTTPException, Depends
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError
from app.database import SessionLocal
from app.models.corpdiary import (
    Bonus,
    Split,
    Div,
    BonusUpload,
    SplitUpload,
    DivUpload,
)
from fastapi.responses import FileResponse
from fastapi import Path
import pandas as pd
import uuid
import shutil
import os
from datetime import datetime
from typing import List
from app.schemas.heatmap import UploadBase

router = APIRouter(prefix="/corpdiary", tags=["corpdiary"])

UPLOAD_FOLDER = "uploads/heatmap"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# ---------------- DB Dependency ----------------
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# ---------------- CSV Columns (CSV HAS ID, BUT WE IGNORE IT) ----------------
SPLIT_COLUMNS = ["ID", "ISIN", "OLD_FV", "NEW_FV", "EX_DT", "INDIC"]
BONUS_COLUMNS = ["ID", "ISIN", "BONUS", "PRE", "EX_DT", "INDIC"]
DIV_COLUMNS = ["ID", "ISIN", "DIV_RATE", "DIV_TYPE", "EX_DT"]

# ---------------- Maps ----------------
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

# ---------------- Upload CSV ----------------
@router.post("/upload/")
async def upload_file(
    upload_date: str = Form(...),
    data_date: str = Form(...),
    data_type: str = Form(...),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    data_type = data_type.lower()

    if data_type not in TABLE_MAP:
        raise HTTPException(status_code=400, detail="Invalid data_type")

    if not file.filename.lower().endswith(".csv"):
        raise HTTPException(status_code=400, detail="Only CSV files allowed")

    Model, UploadModel, expected_columns = TABLE_MAP[data_type]

    # ---------- Save file ----------
    file_path = os.path.join(UPLOAD_FOLDER, f"{uuid.uuid4()}.csv")
    with open(file_path, "wb") as f:
        shutil.copyfileobj(file.file, f)

    # ---------- Read CSV ----------
    try:
        df = pd.read_csv(file_path, header=None, encoding="utf-8")
    except UnicodeDecodeError:
        df = pd.read_csv(file_path, header=None, encoding="latin1")

    if df.shape[1] != len(expected_columns):
        raise HTTPException(
            status_code=400,
            detail=f"Expected {len(expected_columns)} columns, got {df.shape[1]}",
        )

    df.columns = expected_columns
    df = df.where(pd.notnull(df), None)

    model_columns = set(Model.__table__.columns.keys())
    objects = []

    # ---------- Build ORM objects (IGNORE ID) ----------
    for _, row in df.iterrows():
        record = {
            col: row[col]
            for col in expected_columns
            if col in model_columns and col != "ID"
        }
        objects.append(Model(**record))

    if not objects:
        raise HTTPException(status_code=400, detail="No valid rows found")

    # ---------- Save upload metadata ----------
    upload_entry = UploadModel(
        group_id=str(uuid.uuid4()),
        upload_date=datetime.strptime(upload_date, "%Y-%m-%d").date(),
        data_date=datetime.strptime(data_date, "%Y-%m-%d").date(),
        data_type=data_type,
        file_name=file.filename,
        file_path=file_path,
    )

    try:
        db.add(upload_entry)
        db.bulk_save_objects(objects)
        db.commit()
    except SQLAlchemyError as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))

    return {
        "status": "success",
        "data_type": data_type,
        "file": file.filename,
        "rows_inserted": len(objects),
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

    df = pd.read_csv(latest.file_path, header=None)
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

    df = pd.read_csv(latest.file_path, header=None)
    df.columns = expected_columns
    df = df.where(pd.notnull(df), None)

    df["ISIN"] = df["ISIN"].astype(str).str.strip()
    isin = isin.strip()

    filtered = df[df["ISIN"] == isin]

    if filtered.empty:
        raise HTTPException(status_code=404, detail="No records found for this ISIN")

    return filtered.to_dict(orient="records")
@router.get("/{data_type}/files/{upload_id}", response_class=FileResponse)
def download_file(
    data_type: str = Path(..., description="Type of data: bonus,dividend,split"),
    upload_id: int = Path(..., description="ID of the uploaded file"),
    db: Session = Depends(get_db)
):
    data_type = data_type.lower()
    if data_type not in UPLOAD_TABLES:
        raise HTTPException(status_code=400, detail="Invalid data_type")

    UploadModel = UPLOAD_TABLES[data_type]
    upload = db.query(UploadModel).filter(UploadModel.id == upload_id).first()

    if not upload or not os.path.exists(upload.file_path):
        raise HTTPException(status_code=404, detail="File not found")

    return FileResponse(
        path=upload.file_path,
        filename=upload.file_name,
        media_type="application/octet-stream"
    )



# ---------------- Update upload metadata ----------------
@router.put("/{data_type}/{upload_id}/", response_model=dict)
async def update_upload(
    data_type: str,
    upload_id: int,
    upload_date: str = Form(None),
    data_date: str = Form(None),
    new_data_type: str = Form(None),  # allows changing type
    file: UploadFile = File(None),    # allows updating the file
    db: Session = Depends(get_db),
):
    data_type = data_type.lower()
    if data_type not in UPLOAD_TABLES:
        raise HTTPException(status_code=400, detail="Invalid original data_type")

    UploadModel = UPLOAD_TABLES[data_type]
    upload = db.query(UploadModel).filter(UploadModel.id == upload_id).first()
    if not upload:
        raise HTTPException(status_code=404, detail="Upload not found")

    # ---------- Update dates ----------
    if upload_date:
        upload.upload_date = datetime.strptime(upload_date, "%Y-%m-%d").date()
    if data_date:
        upload.data_date = datetime.strptime(data_date, "%Y-%m-%d").date()

    # ---------- Update data_type ----------
    if new_data_type:
        new_data_type = new_data_type.lower()
        if new_data_type not in UPLOAD_TABLES:
            raise HTTPException(status_code=400, detail="Invalid new data_type")
        upload.data_type = new_data_type

    # ---------- Update file ----------
    if file:
        if not file.filename.lower().endswith(".csv"):
            raise HTTPException(status_code=400, detail="Only CSV files allowed")

        # Save new file
        file_path = os.path.join(UPLOAD_FOLDER, f"{uuid.uuid4()}.csv")
        with open(file_path, "wb") as f:
            shutil.copyfileobj(file.file, f)

        # Optionally delete old file
        if os.path.exists(upload.file_path):
            os.remove(upload.file_path)
        upload.file_name = file.filename
        upload.file_path = file_path

    db.commit()
    db.refresh(upload)
    return {
        "id": upload.id,
        "upload_date": str(upload.upload_date),
        "data_date": str(upload.data_date),
        "data_type": upload.data_type,
        "file_name": upload.file_name,
        "file_path": upload.file_path
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

    if os.path.exists(upload.file_path):
        os.remove(upload.file_path)

    db.delete(upload)
    db.commit()

    return {"status": "deleted", "id": upload_id}
