from fastapi import APIRouter, UploadFile, File, Form, HTTPException, Depends, Path
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError
from app.database import SessionLocal
from app.models.heatmap import (
    HouseUpload, CompanyUpload, IndustryUpload, SectorUpload,
    House, Company, Industry, Sector
)
from app.schemas.heatmap import UploadBase
from app.s3_utils import upload_file_to_s3, delete_file_from_s3, get_file_stream_from_s3
from typing import List
import pandas as pd
from datetime import datetime
import uuid
import io 


router = APIRouter(prefix="/heatmap", tags=["heatmap"])

# ---------------- Model + Upload mapping ----------------
TABLE_MAP = {
    "company": (Company, CompanyUpload),
    "house": (House, HouseUpload),
    "industry": (Industry, IndustryUpload),
    "sector": (Sector, SectorUpload),
}
UPLOAD_TABLES = {
    "company": CompanyUpload,
    "house": HouseUpload,
    "industry": IndustryUpload,
    "sector": SectorUpload,
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
HOUSE_COLUMNS = ["ID", "RNK", "IH_PR", "IH_AF", "HOUSE", "COS", "MCAP","DAYCHCR","CH","FFLOAT","FFRNK","WKCHCR","WKCH","MTHCHCR","MTHCH","QTRCHCR","QTRCH","HYCHCR","HYCH","YRCHCR","YRCH"]
INDUSTRY_COLUMNS = ["ID","RNK","INDUSTRY","COS","MCAP","DAYCHCR","CH","FFLOAT","FFRNK","WKCHCR","WKCH","MTHCHCR","MTHCH","QTRCHCR","QTRCH","HYCHCR","HYCH","YRCHCR","YRCH","SECID","ISCCODE"]
SECTOR_COLUMNS = ["ID","RNK","SECTOR","COS","MCAP","DAYCHCR","CH","FFLOAT","FFRNK","WKCHCR","WKCH","MTHCHCR","MTHCH","QTRCHCR","QTRCH","HYCHCR","HYCH","YRCHCR","YRCH","SECID"]

COLUMN_MAP = {
    "company": COMPANY_COLUMNS,
    "house": HOUSE_COLUMNS,
    "industry": INDUSTRY_COLUMNS,
    "sector": SECTOR_COLUMNS,
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
        raise HTTPException(status_code=400, detail="Invalid data_type. Use company, house, industry, or sector.")
    if not file.filename.lower().endswith(".csv"):
        raise HTTPException(status_code=400, detail="Only CSV files allowed")

    Model, UploadModel = TABLE_MAP[data_type]
    expected_columns = COLUMN_MAP[data_type]

    # ---------- Read file into memory ----------
    contents = await file.read()
    file_like = io.BytesIO(contents)

    # ---------- Upload to S3 ----------
    s3_key = upload_file_to_s3(
    file_obj=io.BytesIO(await file.read()),
    filename=file.filename,
    folder=f"corpdiary/{data_type}"
)

    upload_date_obj = datetime.strptime(upload_date, "%Y-%m-%d").date()
    data_date_obj = datetime.strptime(data_date, "%Y-%m-%d").date()

    # ---------- Save upload metadata ----------
    upload_entry = UploadModel(
        group_id=str(uuid.uuid4()),
        upload_date=upload_date_obj,
        data_date=data_date_obj,
        data_type=data_type,
        file_name=file.filename,
        file_path=s3_key,  # store S3 key
    )
    db.add(upload_entry)
    db.commit()
    db.refresh(upload_entry)

    # ---------- Read CSV into DataFrame ----------
    file_like.seek(0)
    try:
        df = pd.read_csv(file_like, header=None, encoding="utf-8")
    except UnicodeDecodeError:
        file_like.seek(0)
        df = pd.read_csv(file_like, header=None, encoding="latin1")

    if df.shape[1] != len(expected_columns):
        raise HTTPException(
            status_code=400,
            detail=f"{data_type} CSV column mismatch: expected {len(expected_columns)}, got {df.shape[1]}"
        )

    df.columns = expected_columns
    df = df.where(pd.notnull(df), None)

    # ---------- Prepare objects for DB ----------
    model_columns = set(Model.__table__.columns.keys())
    objects = []
    for _, row in df.iterrows():
        record = {col: row[col] for col in expected_columns if col in model_columns and col != "pk_id"}
        objects.append(Model(**record))

    if not objects:
        raise HTTPException(status_code=400, detail="No valid rows found")

    # ---------- Bulk insert ----------
    db.bulk_save_objects(objects)
    db.commit()

    return {
        "status": "success",
        "data_type": data_type,
        "file": file.filename,
        "s3_key": s3_key,
        "rows_inserted": len(objects),
    }
    
@router.get("/{data_type}/", response_model=List[UploadBase])
def get_all_uploads(data_type: str, db: Session = Depends(get_db)):
    data_type = data_type.lower()
    if data_type not in UPLOAD_TABLES:
        raise HTTPException(status_code=400, detail="Invalid data_type")
    
    UploadModel = UPLOAD_TABLES[data_type]
    uploads = db.query(UploadModel).order_by(UploadModel.upload_date.desc()).all()
    return uploads  # Pydantic handles conversion

# ---------------- Latest Upload (all records) ----------------
@router.get("/{data_type}/latest-data-file/", response_model=list)
def get_latest_upload_data_file(data_type: str, db: Session = Depends(get_db)):
    data_type = data_type.lower()
    if data_type not in UPLOAD_TABLES:
        raise HTTPException(status_code=400, detail="Invalid data_type")

    UploadModel = UPLOAD_TABLES[data_type]
    latest_upload = db.query(UploadModel).order_by(UploadModel.data_date.desc()).first()
    if not latest_upload:
        raise HTTPException(status_code=404, detail="No uploads found")

    # Read CSV directly from S3
    file_stream = get_file_stream_from_s3(latest_upload.file_path)
    try:
        df = pd.read_csv(file_stream, header=None, encoding="utf-8")
    except UnicodeDecodeError:
        df = pd.read_csv(file_stream, header=None, encoding="latin1")

    df = df.where(pd.notnull(df), None)
    expected_columns = COLUMN_MAP.get(data_type)

    # Adjust column length
    if expected_columns:
        if len(df.columns) > len(expected_columns):
            extra = len(df.columns) - len(expected_columns)
            df.columns = expected_columns + [f"extra_{i}" for i in range(extra)]
        elif len(df.columns) < len(expected_columns):
            missing = len(expected_columns) - len(df.columns)
            df.columns = df.columns.tolist() + [f"col_{i}" for i in range(missing)]
        else:
            df.columns = expected_columns

    return df.to_dict(orient="records")

# ---------------- Latest Upload by ISIN ----------------
@router.get("/{data_type}/latest-data-file/{isin}", response_model=list)
def get_latest_upload_data_file_by_isin(data_type: str, isin: str, db: Session = Depends(get_db)):
    data_type = data_type.lower()
    if data_type not in UPLOAD_TABLES:
        raise HTTPException(status_code=400, detail="Invalid data_type")

    UploadModel = UPLOAD_TABLES[data_type]
    latest_upload = db.query(UploadModel).order_by(UploadModel.data_date.desc()).first()
    if not latest_upload:
        raise HTTPException(status_code=404, detail="No uploads found")

    file_stream = get_file_stream_from_s3(latest_upload.file_path)
    try:
        df = pd.read_csv(file_stream, header=None, encoding="utf-8")
    except UnicodeDecodeError:
        df = pd.read_csv(file_stream, header=None, encoding="latin1")

    df = df.where(pd.notnull(df), None)
    expected_columns = COLUMN_MAP.get(data_type)

    if expected_columns:
        if len(df.columns) > len(expected_columns):
            extra = len(df.columns) - len(expected_columns)
            df.columns = expected_columns + [f"extra_{i}" for i in range(extra)]
        elif len(df.columns) < len(expected_columns):
            missing = len(expected_columns) - len(df.columns)
            df.columns = df.columns.tolist() + [f"col_{i}" for i in range(missing)]
        else:
            df.columns = expected_columns

    isin_col = "ISIN" if "ISIN" in df.columns else df.columns[0]
    df[isin_col] = df[isin_col].astype(str).str.strip()
    filtered_df = df[df[isin_col] == isin.strip()]

    if filtered_df.empty:
        raise HTTPException(status_code=404, detail=f"No records found for ISIN {isin}")

    return filtered_df.to_dict(orient="records")

# ---------------- Update Upload ----------------
from io import BytesIO

@router.put("/{data_type}/{upload_id}/", response_model=dict)
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
        raise HTTPException(status_code=400, detail="Invalid original data_type")

    UploadModel = UPLOAD_TABLES[data_type]
    upload = db.query(UploadModel).filter(UploadModel.id == upload_id).first()
    if not upload:
        raise HTTPException(status_code=404, detail="Upload not found")

    # Update metadata
    if upload_date:
        try:
          upload.upload_date = datetime.strptime(upload_date, "%Y-%m-%d").date()
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid upload_date format: {upload_date}. Expected YYYY-MM-DD")
    if data_date:
        try:
            upload.data_date = datetime.strptime(data_date, "%Y-%m-%d").date()
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid data_date format: {data_date}. Expected YYYY-MM-DD")
            
    if new_data_type:
        new_data_type = new_data_type.lower()
        if new_data_type not in UPLOAD_TABLES:
            raise HTTPException(status_code=400, detail="Invalid new data_type")
        upload.data_type = new_data_type

    # Handle file replacement
    if file:
        if not file.filename.lower().endswith(".csv"):
            raise HTTPException(status_code=400, detail="Only CSV files allowed")

        # Delete old file from S3
        delete_file_from_s3(upload.file_path)

        # Read UploadFile into memory and wrap in BytesIO
        file_bytes = await file.read()
        file_like = BytesIO(file_bytes)

        # Upload to S3
        s3_key = upload_file_to_s3(
            file_obj=file_like,
            folder=f"heatmap/{data_type}",
            filename=file.filename
        )

        # Update DB fields
        upload.file_name = file.filename
        upload.file_path = s3_key

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

    # Delete from S3
    delete_file_from_s3(upload.file_path)

    db.delete(upload)
    db.commit()

    return {"status": "deleted", "id": upload_id}

# ---------------- Download file ----------------
@router.get("/{data_type}/files/{upload_id}/")
def download_file(data_type: str, upload_id: int, db: Session = Depends(get_db)):
    data_type = data_type.lower()
    if data_type not in UPLOAD_TABLES:
        raise HTTPException(status_code=400, detail="Invalid data_type")

    UploadModel = UPLOAD_TABLES[data_type]
    upload = db.query(UploadModel).filter(UploadModel.id == upload_id).first()
    if not upload:
        raise HTTPException(status_code=404, detail="Upload not found")

    # Stream file from S3
    file_stream = get_file_stream_from_s3(upload.file_path)
    return file_stream  # can wrap in StreamingResponse if needed