from fastapi import APIRouter, UploadFile, File, Form, HTTPException, Depends
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError
from app.database import SessionLocal
from app.models.heatmap import (
    HouseUpload,
    CompanyUpload,
    IndustryUpload,
    House,
    Company,
    Industry,
)
import pandas as pd
import uuid
import shutil
import os
from datetime import datetime
from typing import List
from datetime import date
from app.schemas.heatmap import UploadBase

router = APIRouter(prefix="/heatmap", tags=["heatmap"])

UPLOAD_FOLDER = "uploads/heatmap"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# ---------------- Model + Upload mapping ----------------
TABLE_MAP = {
    "company": (Company, CompanyUpload),
    "house": (House, HouseUpload),
    "industry": (Industry, IndustryUpload),
}
UPLOAD_TABLES = {
    "company": CompanyUpload,
    "house": HouseUpload,
    "industry": IndustryUpload,
}

# ---------------- CSV column order (NO HEADERS) ----------------
COMPANY_COLUMNS = [
    "ID","RANK", "COMPANY", "MCAP", "DAYCHCR", "CH", "FFLOAT", "FFRNK",
    "WKCHCR", "WKCH", "MTHCHCR", "MTHCH", "QTRCHCR", "QTRCH",
    "HYCHCR", "HYCH", "YRCHCR", "YRCH", "CMP", "PCL", "CH_RS",
    "CH_PER", "OPEN", "HIGH", "LOW", "CLOSE", "VOL", "VALUE",
    "TRADE", "ISIN", "SEC_ID", "ISCCODE", "INDUSTRY", "IND_RNK",
    "IH_MCODE", "IH_MNAME", "HOU_RNK", "COMPANY_NAME", "BSE",
    "NSE", "INDEX_STK", "RONW", "ROCE", "EPS", "CEPS", "P_E",
    "P_CE", "DIV", "YLD", "DEBT_EQ",
]

HOUSE_COLUMNS = [
    "ID", "RNK", "IH_PR", "IH_AF", "HOUSE", "COS",
    "MCAP", "DAYCHCR", "CH", "FFLOAT", "FFRNK",
    "WKCHCR", "WKCH", "MTHCHCR", "MTHCH",
    "QTRCHCR", "QTRCH", "HYCHCR", "HYCH",
    "YRCHCR", "YRCH",
]

INDUSTRY_COLUMNS = [
    "ID", "RNK", "INDUSTRY", "COS", "MCAP", "DAYCHCR", "CH",
    "FFLOAT", "FFRNK", "WKCHCR", "WKCH",
    "MTHCHCR", "MTHCH", "QTRCHCR", "QTRCH",
    "HYCHCR", "HYCH", "YRCHCR", "YRCH",
    "SECID", "ISCCODE",
]

COLUMN_MAP = {
    "company": COMPANY_COLUMNS,
    "house": HOUSE_COLUMNS,
    "industry": INDUSTRY_COLUMNS,
}

# ---------------- DB Dependency ----------------
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# ---------------- Upload API ----------------
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
        raise HTTPException(
            status_code=400,
            detail="Invalid data_type. Use company, house, or industry.",
        )

    if not file.filename.lower().endswith(".csv"):
        raise HTTPException(status_code=400, detail="Only CSV files allowed")

    Model, UploadModel = TABLE_MAP[data_type]
    expected_columns = COLUMN_MAP[data_type]

    # ---------- Save file ----------
    file_path = os.path.join(UPLOAD_FOLDER, f"{uuid.uuid4()}.csv")
    with open(file_path, "wb") as f:
        shutil.copyfileobj(file.file, f)

    upload_date = datetime.strptime(upload_date, "%Y-%m-%d").date()
    data_date = datetime.strptime(data_date, "%Y-%m-%d").date()

    # ---------- Save upload metadata ----------
    upload_entry = UploadModel(
        group_id=str(uuid.uuid4()),
        upload_date=upload_date,
        data_date=data_date,
        data_type=data_type,
        file_name=file.filename,
        file_path=file_path,
    )
    db.add(upload_entry)
    db.commit()

    # ---------- Read CSV (NO HEADERS) ----------
    try:
        df = pd.read_csv(file_path, header=None, encoding="utf-8")
    except UnicodeDecodeError:
        df = pd.read_csv(file_path, header=None, encoding="latin1")

    if df.shape[1] != len(expected_columns):
        raise HTTPException(
            status_code=400,
            detail=(
                f"{data_type} CSV column mismatch: "
                f"expected {len(expected_columns)}, got {df.shape[1]}"
            ),
        )

    df.columns = expected_columns
    df = df.where(pd.notnull(df), None)

    model_columns = set(Model.__table__.columns.keys())
    objects = []

    for _, row in df.iterrows():
        record = {
            col: row[col]
            for col in expected_columns
            if col in model_columns and col != "pk_id"
        }
        objects.append(Model(**record))

    if not objects:
        raise HTTPException(status_code=400, detail="No valid rows found")

    # ---------- Bulk insert ----------
    try:
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
# Get all uploads
@router.get("/{data_type}/", response_model=List[UploadBase])
def get_all_uploads(data_type: str, db: Session = Depends(get_db)):
    data_type = data_type.lower()
    if data_type not in UPLOAD_TABLES:
        raise HTTPException(status_code=400, detail="Invalid data_type")
    
    UploadModel = UPLOAD_TABLES[data_type]
    uploads = db.query(UploadModel).order_by(UploadModel.upload_date.desc()).all()
    return uploads  # Pydantic will handle conversion automatically

# Latest upload (must come before the dynamic {upload_id} route)
# ---------------- Latest upload (all records) ----------------
@router.get("/{data_type}/latest-data-file/", response_model=list)
def get_latest_upload_data_file(data_type: str, db: Session = Depends(get_db)):
    data_type = data_type.lower()
    if data_type not in UPLOAD_TABLES:
        raise HTTPException(status_code=400, detail="Invalid data_type")

    UploadModel = UPLOAD_TABLES[data_type]

    latest_upload = db.query(UploadModel).order_by(UploadModel.data_date.desc()).first()
    if not latest_upload:
        raise HTTPException(status_code=404, detail="No uploads found")

    file_path = latest_upload.file_path

    # Choose columns based on type
    expected_columns = COLUMN_MAP.get(data_type)

    # ---------- Safe CSV reading ----------
    try:
        try:
            df = pd.read_csv(file_path, header=None, encoding="utf-8")
        except UnicodeDecodeError:
            df = pd.read_csv(file_path, header=None, encoding="latin1")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to read CSV: {e}")

    df = df.where(pd.notnull(df), None)

    # ---------- Fix column length ----------
    if expected_columns:
        if len(df.columns) > len(expected_columns):
            extra = len(df.columns) - len(expected_columns)
            expected_columns_extended = expected_columns + [f"extra_{i}" for i in range(extra)]
            df.columns = expected_columns_extended
        elif len(df.columns) < len(expected_columns):
            missing = len(expected_columns) - len(df.columns)
            df.columns = df.columns.tolist() + [f"col_{i}" for i in range(missing)]
        else:
            df.columns = expected_columns

    return df.to_dict(orient="records")


# ---------------- Latest upload by ISIN ----------------
@router.get("/{data_type}/latest-data-file/{isin}", response_model=list)
def get_latest_upload_data_file_by_isin(data_type: str, isin: str, db: Session = Depends(get_db)):
    data_type = data_type.lower()
    if data_type not in UPLOAD_TABLES:
        raise HTTPException(status_code=400, detail="Invalid data_type")

    UploadModel = UPLOAD_TABLES[data_type]

    latest_upload = db.query(UploadModel).order_by(UploadModel.data_date.desc()).first()
    if not latest_upload:
        raise HTTPException(status_code=404, detail="No uploads found")

    file_path = latest_upload.file_path
    expected_columns = COLUMN_MAP.get(data_type)

    # ---------- Safe CSV reading ----------
    try:
        try:
            df = pd.read_csv(file_path, header=None, encoding="utf-8")
        except UnicodeDecodeError:
            df = pd.read_csv(file_path, header=None, encoding="latin1")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to read CSV: {e}")

    df = df.where(pd.notnull(df), None)

    # ---------- Fix column length ----------
    if expected_columns:
        if len(df.columns) > len(expected_columns):
            extra = len(df.columns) - len(expected_columns)
            expected_columns_extended = expected_columns + [f"extra_{i}" for i in range(extra)]
            df.columns = expected_columns_extended
        elif len(df.columns) < len(expected_columns):
            missing = len(expected_columns) - len(df.columns)
            df.columns = df.columns.tolist() + [f"col_{i}" for i in range(missing)]
        else:
            df.columns = expected_columns

    # ---------- Filter by ISIN ----------
    isin_col = "ISIN" if "ISIN" in df.columns else df.columns[0]
    df[isin_col] = df[isin_col].astype(str).str.strip()
    isin = isin.strip()
    filtered_df = df[df[isin_col] == isin]


    if filtered_df.empty:
        raise HTTPException(status_code=404, detail=f"No records found for ISIN {isin}")

    return filtered_df.to_dict(orient="records")


# ---------------- Get single upload ----------------
@router.get("/{data_type}/{upload_id}/", response_model=UploadBase)
def get_upload(data_type: str, upload_id: int, db: Session = Depends(get_db)):
    data_type = data_type.lower()
    if data_type not in UPLOAD_TABLES:
        raise HTTPException(status_code=400, detail="Invalid data_type")
    
    UploadModel = UPLOAD_TABLES[data_type]
    upload = db.query(UploadModel).filter(UploadModel.id == upload_id).first()
    if not upload:
        raise HTTPException(status_code=404, detail="Upload not found")
    
    return upload  # no __dict__, Pydantic handles it


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
@router.delete("/{data_type}/{upload_id}/", response_model=dict)
def delete_upload(data_type: str, upload_id: int, db: Session = Depends(get_db)):
    data_type = data_type.lower()
    if data_type not in UPLOAD_TABLES:
        raise HTTPException(status_code=400, detail="Invalid data_type")

    UploadModel = UPLOAD_TABLES[data_type]
    upload = db.query(UploadModel).filter(UploadModel.id == upload_id).first()
    if not upload:
        raise HTTPException(status_code=404, detail="Upload not found")
    
    db.delete(upload)
    db.commit()
    return {"status": "deleted", "id": upload_id}


