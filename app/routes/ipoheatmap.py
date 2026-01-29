from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from sqlalchemy.orm import Session
from typing import List
from datetime import date
from uuid import uuid4
import os
import pandas as pd
from fastapi.responses import FileResponse
from fastapi import Query
from sqlalchemy import extract
from app.database import SessionLocal
from app.models.ipoheatmap import (
    IPOHeatmapYear,
    IPOHeatmapYearUpload,
    IPOHeatmapData,
    IPOHeatmapDataUpload,
)
from app.schemas.ipoheatmap import (
    IPOHeatmapYearCreate,
    IPOHeatmapYearRead,
    IPOHeatmapYearUploadRead,
    IPOHeatmapDataCreate,
    IPOHeatmapDataRead,
    IPOHeatmapDataUploadRead,
)

UPLOAD_DIR = "uploads/ipoheatmap"
os.makedirs(UPLOAD_DIR, exist_ok=True)

router = APIRouter(
    prefix="/ipoheatmap",
    tags=["IPO Heatmap"],
)

# -------------------- Database Session --------------------
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# -------------------------
# YEAR ROUTES
# -------------------------
@router.post("/year/upload-file", response_model=IPOHeatmapYearUploadRead)
async def upload_year_file(
    file: UploadFile = File(...), 
    upload_date: date = Form(...),
    data_date: date = Form(...),
    db: Session = Depends(get_db)
):
    if not file.filename.endswith((".csv", ".xlsx")):
        raise HTTPException(status_code=400, detail="Invalid file type")
    
    file_path = os.path.join(UPLOAD_DIR, "year", file.filename)
    os.makedirs(os.path.dirname(file_path), exist_ok=True)
    
    # Save uploaded file
    with open(file_path, "wb") as f:
        f.write(await file.read())
    
    # Read file without header and drop first column
    df = pd.read_csv(file_path, header=None) if file.filename.endswith(".csv") else pd.read_excel(file_path, header=None)
    df = df.iloc[:, 1:]
    df.columns = ["year", "cos", "ipo_value", "market_value", "ch_per"]

    # Insert rows into DB
    try:
        for _, row in df.iterrows():
            year_obj = IPOHeatmapYear(
                year=int(row["year"]),
                cos=int(row["cos"]),
                ipo_value=float(row["ipo_value"]),
                market_value=float(row["market_value"]),
                ch_per=float(row["ch_per"]),
            )
            db.add(year_obj)
        db.commit()
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Error inserting year data: {e}")

    # Record upload
    upload_obj = IPOHeatmapYearUpload(
        upload_date=upload_date,
        data_date=data_date,
        data_type="Year CSV/Excel",
        file_name=file.filename,
        file_path=file_path,
    )
    db.add(upload_obj)
    db.commit()
    db.refresh(upload_obj)
    
    return upload_obj


@router.get("/year/latest", response_model=List[IPOHeatmapYearRead])
def get_latest_year_data(db: Session = Depends(get_db)):
    latest_upload = db.query(IPOHeatmapYearUpload).order_by(IPOHeatmapYearUpload.data_date.desc()).first()
    if not latest_upload:
        raise HTTPException(status_code=404, detail="No year upload data found")

    # Return all years assuming they belong to the latest upload
    years = db.query(IPOHeatmapYear).all()
    if not years:
        raise HTTPException(status_code=404, detail="No year data found")
    
    return years


# Update year upload by upload ID
@router.put("/year/uploads/{upload_id}", response_model=IPOHeatmapYearUploadRead)
async def update_year_upload(
    upload_id: int,
    file: UploadFile = File(None),
    upload_date: date | None = Form(None),
    data_date: date | None = Form(None),
    db: Session = Depends(get_db)
):
    upload = db.query(IPOHeatmapYearUpload).filter(IPOHeatmapYearUpload.id == upload_id).first()
    if not upload:
        raise HTTPException(status_code=404, detail="Year upload not found")
    
    if upload_date:
        upload.upload_date = upload_date
    if data_date:
        upload.data_date = data_date
    if file:
        if upload.file_path and os.path.exists(upload.file_path):
            os.remove(upload.file_path)

        filename = f"{date.today()}_{uuid4()}_{file.filename}"
        file_path = os.path.join(UPLOAD_DIR, "year", filename)
        os.makedirs(os.path.dirname(file_path), exist_ok=True)
        with open(file_path, "wb") as f:
            f.write(await file.read())

        upload.file_name = filename
        upload.file_path = file_path

    db.commit()
    db.refresh(upload)
    return upload


@router.delete("/year/uploads/{upload_id}")
def delete_year_upload(upload_id: int, db: Session = Depends(get_db)):
    upload_obj = db.query(IPOHeatmapYearUpload).filter(IPOHeatmapYearUpload.id == upload_id).first()
    if not upload_obj:
        raise HTTPException(status_code=404, detail="Year upload not found")
    
    if os.path.exists(upload_obj.file_path):
        os.remove(upload_obj.file_path)
    
    db.delete(upload_obj)
    db.commit()
    return {"detail": "Year upload deleted successfully"}


@router.get("/year/uploads", response_model=List[IPOHeatmapYearUploadRead])
def get_year_uploads(db: Session = Depends(get_db)):
    return db.query(IPOHeatmapYearUpload).order_by(IPOHeatmapYearUpload.upload_date.desc()).all()

# Download Year upload file
@router.get("/year/download/{upload_id}")
def download_year_file(upload_id: int, db: Session = Depends(get_db)):
    upload_obj = db.query(IPOHeatmapYearUpload).filter(IPOHeatmapYearUpload.id == upload_id).first()
    if not upload_obj:
        raise HTTPException(status_code=404, detail="Year upload not found")
    
    if not os.path.exists(upload_obj.file_path):
        raise HTTPException(status_code=404, detail="File not found on server")
    
    return FileResponse(
        path=upload_obj.file_path,
        filename=upload_obj.file_name,
        media_type="application/octet-stream"
    )
# -------------------------
# DATA ROUTES
# -------------------------
@router.post("/data/upload-file", response_model=IPOHeatmapDataUploadRead)
async def upload_data_file(
    file: UploadFile = File(...), 
    upload_date: date = Form(...),
    data_date: date = Form(...),
    db: Session = Depends(get_db)
):
    if not file.filename.endswith((".csv", ".xlsx")):
        raise HTTPException(status_code=400, detail="Invalid file type")
    
    file_path = os.path.join(UPLOAD_DIR, "data", file.filename)
    os.makedirs(os.path.dirname(file_path), exist_ok=True)
    
    # Save file
    with open(file_path, "wb") as f:
        f.write(await file.read())
    
    # Read file without header, drop first column
    df = pd.read_csv(file_path, header=None) if file.filename.endswith(".csv") else pd.read_excel(file_path, header=None)
    df = df.iloc[:, 1:]
    df.columns = ["company", "iss_open", "offer_price", "cmp", "ipo_value", "cur_value", "gain_per"]

    # Insert rows into DB
    try:
        for _, row in df.iterrows():
            data_obj = IPOHeatmapData(
                company=row["company"],
                iss_open=pd.to_datetime(row["iss_open"]),
                offer_price=float(row["offer_price"]),
                cmp=float(row["cmp"]),
                ipo_value=float(row["ipo_value"]),
                cur_value=float(row["cur_value"]),
                gain_per=float(row["gain_per"]),
            )
            db.add(data_obj)
        db.commit()
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Error inserting data: {e}")

    # Record upload
    upload_obj = IPOHeatmapDataUpload(
        upload_date=upload_date,
        data_date=data_date,
        data_type="Data CSV/Excel",
        file_name=file.filename,
        file_path=file_path,
    )
    db.add(upload_obj)
    db.commit()
    db.refresh(upload_obj)
    return upload_obj


@router.get("/data/latest", response_model=List[IPOHeatmapDataRead])
def get_latest_data(db: Session = Depends(get_db)):
    latest_upload = db.query(IPOHeatmapDataUpload).order_by(IPOHeatmapDataUpload.data_date.desc()).first()
    if not latest_upload:
        raise HTTPException(status_code=404, detail="No data upload found")

    # Return all data assuming latest upload
    data = db.query(IPOHeatmapData).all()
    if not data:
        raise HTTPException(status_code=404, detail="No data found")
    
    return data
# Get year-wise data based on year
@router.get("/data/yearwise", response_model=List[IPOHeatmapDataRead])
def get_data_by_year(year: int = Query(..., description="Year to filter IPO data"), db: Session = Depends(get_db)):
    # Filter IPOHeatmapData by year extracted from iss_open
    data = db.query(IPOHeatmapData).filter(extract('year', IPOHeatmapData.iss_open) == year).all()
    
    if not data:
        raise HTTPException(status_code=404, detail=f"No IPO data found for year {year}")
    
    return data
@router.put("/data/uploads/{upload_id}", response_model=IPOHeatmapDataUploadRead)
async def update_data_upload(
    upload_id: int,
    file: UploadFile = File(None),
    upload_date: date | None = Form(None),
    data_date: date | None = Form(None),
    db: Session = Depends(get_db)
):
    upload = db.query(IPOHeatmapDataUpload).filter(IPOHeatmapDataUpload.id == upload_id).first()
    if not upload:
        raise HTTPException(status_code=404, detail="Data upload not found")
    
    if upload_date:
        upload.upload_date = upload_date
    if data_date:
        upload.data_date = data_date
    if file:
        if upload.file_path and os.path.exists(upload.file_path):
            os.remove(upload.file_path)

        filename = f"{date.today()}_{uuid4()}_{file.filename}"
        file_path = os.path.join(UPLOAD_DIR, "data", filename)
        os.makedirs(os.path.dirname(file_path), exist_ok=True)
        with open(file_path, "wb") as f:
            f.write(await file.read())

        upload.file_name = filename
        upload.file_path = file_path

    db.commit()
    db.refresh(upload)
    return upload


@router.delete("/data/uploads/{upload_id}")
def delete_data_upload(upload_id: int, db: Session = Depends(get_db)):
    upload_obj = db.query(IPOHeatmapDataUpload).filter(IPOHeatmapDataUpload.id == upload_id).first()
    if not upload_obj:
        raise HTTPException(status_code=404, detail="Data upload not found")
    
    if os.path.exists(upload_obj.file_path):
        os.remove(upload_obj.file_path)
    
    db.delete(upload_obj)
    db.commit()
    return {"detail": "Data upload deleted successfully"}


@router.get("/data/uploads", response_model=List[IPOHeatmapDataUploadRead])
def get_data_uploads(db: Session = Depends(get_db)):
    return db.query(IPOHeatmapDataUpload).order_by(IPOHeatmapDataUpload.upload_date.desc()).all()


# Download Data upload file
@router.get("/data/download/{upload_id}")
def download_data_file(upload_id: int, db: Session = Depends(get_db)):
    upload_obj = db.query(IPOHeatmapDataUpload).filter(IPOHeatmapDataUpload.id == upload_id).first()
    if not upload_obj:
        raise HTTPException(status_code=404, detail="Year upload not found")
    
    if not os.path.exists(upload_obj.file_path):
        raise HTTPException(status_code=404, detail="File not found on server")
    
    return FileResponse(
        path=upload_obj.file_path,
        filename=upload_obj.file_name,
        media_type="application/octet-stream"
    )
