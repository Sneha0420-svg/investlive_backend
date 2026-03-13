import io
import uuid
from datetime import datetime
from typing import List

import pandas as pd
from fastapi import APIRouter, UploadFile, File, Form, HTTPException, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError

from app.database import SessionLocal
from app.models.heatmap import (
    HouseUpload, CompanyUpload, IndustryUpload, SectorUpload,
    House, Company, Industry, Sector
)
from app.schemas.heatmap import UploadBase
from app.s3_utils import upload_file_to_s3, delete_file_from_s3, get_file_stream_from_s3, get_s3_file_url

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

# ---------------- CSV Reader Helper ----------------
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
        df = pd.read_csv(file_stream, header=None, encoding="latin1", errors="replace")
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

    Model, UploadModel = TABLE_MAP[data_type]
    expected_columns = COLUMN_MAP[data_type]

    contents = await file.read()
    if not contents:
        raise HTTPException(status_code=400, detail="Uploaded file is empty")
    file_like = io.BytesIO(contents)

    df = read_csv_safe(file_like, expected_columns)

    file_like.seek(0)
    try:
        # Correct S3 call: folder must be keyword
        s3_key = upload_file_to_s3(file_obj=file_like, folder=f"heatmap/{data_type}", filename=file.filename)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"S3 upload failed: {e}")

    upload_date_obj = datetime.strptime(upload_date, "%Y-%m-%d").date()
    data_date_obj = datetime.strptime(data_date, "%Y-%m-%d").date()

    upload_entry = UploadModel(
        group_id=str(uuid.uuid4()),
        upload_date=upload_date_obj,
        data_date=data_date_obj,
        data_type=data_type,
        file_name=file.filename,
        file_path=s3_key,
    )

    model_columns = set(Model.__table__.columns.keys())
    objects = []
    for _, row in df.iterrows():
        record = {col: row[col] for col in expected_columns if col in model_columns and col != "pk_id"}
        objects.append(Model(**record))

    if not objects:
        delete_file_from_s3(s3_key)
        raise HTTPException(status_code=400, detail="No valid rows found in CSV")

    try:
        db.add(upload_entry)
        db.flush()
        db.bulk_save_objects(objects)
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
@router.get("/{data_type}/", response_model=List[UploadBase])
def get_all_uploads(data_type: str, db: Session = Depends(get_db)):
    data_type = data_type.lower()
    if data_type not in UPLOAD_TABLES:
        raise HTTPException(status_code=400, detail="Invalid data_type")

    UploadModel = UPLOAD_TABLES[data_type]
    uploads = db.query(UploadModel).order_by(UploadModel.upload_date.desc()).all()

    uploads_with_url = []
    for upload in uploads:
        upload_dict = upload.__dict__.copy()
        upload_dict["file_url"] = get_s3_file_url(upload.file_path)
        uploads_with_url.append(upload_dict)

    return uploads_with_url

# ---------------- Latest Upload Data ----------------
@router.get("/{data_type}/latest-data-file/", response_model=list)
def get_latest_upload_data_file(data_type: str, db: Session = Depends(get_db)):
    data_type = data_type.lower()
    if data_type not in UPLOAD_TABLES:
        raise HTTPException(status_code=400, detail="Invalid data_type")

    UploadModel = UPLOAD_TABLES[data_type]
    latest_upload = db.query(UploadModel).order_by(UploadModel.data_date.desc()).first()
    if not latest_upload:
        raise HTTPException(status_code=404, detail="No uploads found")

    file_stream = get_file_stream_from_s3(latest_upload.file_path)
    if not file_stream:
        raise HTTPException(status_code=404, detail="File not found in S3")

    df = read_csv_safe(file_stream, COLUMN_MAP[data_type])
    records = df.to_dict(orient="records")

    s3_url = get_s3_file_url(latest_upload.file_path)
    for record in records:
        record["_s3_url"] = s3_url

    return records

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
    if not file_stream:
        raise HTTPException(status_code=404, detail="File not found in S3")

    df = read_csv_safe(file_stream, COLUMN_MAP[data_type])
    isin_col = "ISIN" if "ISIN" in df.columns else df.columns[0]
    df[isin_col] = df[isin_col].astype(str).str.strip()
    filtered_df = df[df[isin_col] == isin.strip()]
    if filtered_df.empty:
        raise HTTPException(status_code=404, detail=f"No records found for ISIN {isin}")

    records = filtered_df.to_dict(orient="records")
    s3_url = get_s3_file_url(latest_upload.file_path)
    for record in records:
        record["_s3_url"] = s3_url

    return records

# ---------------- Download File ----------------
@router.get("/{data_type}/files/{upload_id}/")
def download_file(data_type: str, upload_id: int, db: Session = Depends(get_db)):
    data_type = data_type.lower()
    if data_type not in UPLOAD_TABLES:
        raise HTTPException(400, "Invalid data_type")

    UploadModel = UPLOAD_TABLES[data_type]
    upload = db.query(UploadModel).filter(UploadModel.id == upload_id).first()
    if not upload:
        raise HTTPException(404, "Upload not found")

    file_stream = get_file_stream_from_s3(upload.file_path)
    if not file_stream:
        raise HTTPException(404, "File not found in S3")

    return StreamingResponse(
        file_stream,
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{upload.file_name}"'}
    )

# ---------------- Delete Upload ----------------
@router.delete("/{data_type}/{upload_id}/", response_model=dict)
def delete_upload(data_type: str, upload_id: int, db: Session = Depends(get_db)):
    data_type = data_type.lower()
    if data_type not in UPLOAD_TABLES:
        raise HTTPException(status_code=400, detail="Invalid data_type")

    UploadModel = UPLOAD_TABLES[data_type]
    upload = db.query(UploadModel).filter(UploadModel.id == upload_id).first()
    if not upload:
        raise HTTPException(status_code=404, detail="Upload not found")

    delete_file_from_s3(upload.file_path)
    db.delete(upload)
    db.commit()
    return {"status": "deleted", "id": upload_id}