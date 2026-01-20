# app/routes/marketind.py


import os

from fastapi import APIRouter, Depends, UploadFile, File, HTTPException, Form
from sqlalchemy.orm import Session
import pandas as pd
from app.models.marketind import StockData,MarketIndicatorUpload
from app.database import SessionLocal
import io
from datetime import date
from typing import List
from fastapi.responses import FileResponse
from collections import defaultdict
from typing import Dict, Any
import math
from sqlalchemy import desc

UPLOAD_FOLDER = "uploads"  # folder to store files
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
router = APIRouter( tags=["Market Indicator"])

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@router.post("/upload-data-multiple/")
async def upload_multiple_data(
    files: List[UploadFile] = File(...),
    upload_date: date = Form(...),
    data_date: date = Form(...),
    data_type: str = Form(...),
    db: Session = Depends(get_db)
):
    if not os.path.exists(UPLOAD_FOLDER):
        os.makedirs(UPLOAD_FOLDER)

    all_inserted = []

    for file in files:
        filename = file.filename
        file_path = os.path.join(UPLOAD_FOLDER, filename)

        # Save file to disk
        with open(file_path, "wb") as f:
            f.write(await file.read())

        # Save info to MarketIndicatorUpload table
        upload_record = MarketIndicatorUpload(
            upload_date=upload_date,
            data_date=data_date,
            data_type=data_type,
            file_name=filename,
            file_path=file_path
        )
        db.add(upload_record)
        db.commit()
        db.refresh(upload_record)

        # Read the file content
        with open(file_path, "rb") as f:
            contents = f.read()

        try:
            if filename.endswith((".xlsx", ".xls")):
                df = pd.read_excel(io.BytesIO(contents), header=0)
            elif filename.endswith(".csv"):
                df = pd.read_csv(io.StringIO(contents.decode("utf-8")), header=0)
            else:
                raise HTTPException(status_code=400, detail=f"Invalid file type: {filename}")
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Failed to read file {filename}: {e}")

        if df.shape[1] < 5:
            raise HTTPException(status_code=400, detail=f"{filename} must have at least 5 columns")

        # Rename columns
        df.columns = ["name", "year_ago", "current", "change_percent", "tab_id"] + \
                     [f"extra_{i}" for i in range(df.shape[1]-5)]

        inserted_records = []
        BATCH_SIZE = 20

        # Function to detect if row is a header
        def is_header_row(row):
            # Treat as header if year_ago/current are non-numeric placeholders
            return str(row["year_ago"]).strip() in ["Yr-ago", "0", ""] and \
                   str(row["current"]).strip() in ["Curnt", "0", ""]

        # Insert stock_data tab-wise
        for tab_number, tab_data in df.groupby("tab_id"):
            objects = []
            for _, row in tab_data.iterrows():
                if is_header_row(row):
                    # Header row → store with year_ago/current/change_percent = 0
                    stock = StockData(
                        tab_id=float(row["tab_id"]),
                        name=str(row["name"]).strip(),
                        year_ago=0,
                        current=0,
                        change_percent=0,
                        upload_date=upload_date,
                        data_date=data_date,
                        type=data_type
                    )
                    objects.append(stock)
                    inserted_records.append(stock)
                else:
                    # Normal numeric row
                    try:
                        stock = StockData(
                            tab_id=float(row["tab_id"]),
                            name=str(row["name"]).strip(),
                            year_ago=float(row["year_ago"]),
                            current=float(row["current"]),
                            change_percent=float(row["change_percent"]),
                            upload_date=upload_date,
                            data_date=data_date,
                            type=data_type
                        )
                        objects.append(stock)
                        inserted_records.append(stock)
                    except Exception as e:
                        raise HTTPException(
                            status_code=400,
                            detail=f"Invalid data in tab {tab_number} of file {filename}: {e}"
                        )

                # Commit batch
                if len(objects) >= BATCH_SIZE:
                    db.bulk_save_objects(objects)
                    db.commit()
                    objects = []

            # Commit remaining objects
            if objects:
                db.bulk_save_objects(objects)
                db.commit()

        all_inserted.append({
            "file": filename,
            "records_inserted": len(inserted_records),
            "tabs": df['tab_id'].nunique(),
            "upload_id": upload_record.id,
            "file_link": f"/files/{upload_record.id}"
        })

    return {
        "message": f"Processed {len(files)} files.",
        "details": all_inserted
    }

@router.get("/marketindicator/uploads/", response_model=List[dict])
def get_uploads(db: Session = Depends(get_db)):
    """
    Returns all uploaded files with upload_date, data_date, data_type, and a file link
    """
    uploads = db.query(MarketIndicatorUpload).order_by(MarketIndicatorUpload.upload_date.desc()).all()
    if not uploads:
        raise HTTPException(status_code=404, detail="No uploads found")

    result = []
    for upload in uploads:
        result.append({
            "id": upload.id,
            "upload_date": upload.upload_date,
            "data_date": upload.data_date,
            "data_type": upload.data_type,
            "file_name": upload.file_name,
            "file_link": f"/files/{upload.id}"  # frontend can use this to view/download
        })

    return result

@router.get("/files/{upload_id}")
def download_file(upload_id: int, db: Session = Depends(get_db)):
    """
    Download a file by upload record ID
    """
    record = db.query(MarketIndicatorUpload).filter(MarketIndicatorUpload.id == upload_id).first()
    if not record:
        raise HTTPException(status_code=404, detail="File not found")

    file_path = record.file_path
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="File not found on server")

    return FileResponse(path=file_path, filename=record.file_name, media_type='application/octet-stream')


def is_header_row(stock):
    """
    Detect if a row is a section header:
    - Either name matches section keyword
    - Or all numeric fields are zero/NaN
    """
    year_ago_empty = stock.year_ago is None or (isinstance(stock.year_ago, float) and math.isnan(stock.year_ago)) or stock.year_ago == 0
    current_empty = stock.current is None or (isinstance(stock.current, float) and math.isnan(stock.current)) or stock.current == 0
    change_empty = stock.change_percent is None or (isinstance(stock.change_percent, float) and math.isnan(stock.change_percent)) or stock.change_percent == 0

    return year_ago_empty and current_empty and change_empty

@router.get("/marketindicator/", response_model=Dict[str, Any])
def get_stocks(db: Session = Depends(get_db)):
    latest_upload = db.query(MarketIndicatorUpload).order_by(
        desc(MarketIndicatorUpload.upload_date),
        desc(MarketIndicatorUpload.data_date)
    ).first()

    if not latest_upload:
        raise HTTPException(status_code=404, detail="No uploads found")

    # Step 2: Get all stock data for that latest upload
    stocks = db.query(StockData).filter(
        StockData.upload_date == latest_upload.upload_date,
        StockData.data_date == latest_upload.data_date,
        StockData.type == latest_upload.data_type
    ).order_by(StockData.tab_id, StockData.id).all()
    if not stocks:
        raise HTTPException(status_code=404, detail="No stock data found")

    # Map tab IDs to names
    tab_map = {
        1: "Returns",
        2: "Indices",
        3: "Currencies",
        4: "Commodities"
    }

    # Section headers for each tab
    tab_sections = {
        1: ["India Stocks", "Bullion", "Forex vs INR", "Crude"],
        2: ["BRICS", "Asia/Pacific", "America/Europe"],
        3: ["INR vs.", "USD vs."],
        4: ["Metals (Kg)", "Agro-Indu (100 Kg)"]
    }

    # Initialize result dict
    result = {tab_name: [] for tab_name in tab_map.values()}
    current_section_per_tab = {}

    for stock in stocks:
        tab_name = tab_map.get(stock.tab_id, "Unknown")
        stock_name = stock.name.strip() if stock.name else ""
        sections_for_tab = tab_sections.get(stock.tab_id, [])

        # Detect header: either name is a known section OR numeric columns are empty/zero
        is_header = stock_name in sections_for_tab or is_header_row(stock)

        if is_header:
            # Start a new section
            section_title = stock_name if stock_name in sections_for_tab else stock_name
            section = {"title": section_title, "rows": []}
            result[tab_name].append(section)
            current_section_per_tab[tab_name] = section
        else:
            # Add row to current section
            current_section = current_section_per_tab.get(tab_name)
            if not current_section:
                # Fallback for first row
                current_section = {"title": "(No Title)", "rows": []}
                result[tab_name].append(current_section)
                current_section_per_tab[tab_name] = current_section

            current_section["rows"].append([
                stock.name,
                stock.year_ago,
                stock.current,
                stock.change_percent
            ])

    return result

# GET stocks by tab with new fields
@router.get("/marketindicator/tab/{tab_id}", response_model=List[dict])
def get_stocks_by_tab(tab_id: float, db: Session = Depends(get_db)):
    stocks = db.query(StockData).filter(StockData.tab_id == tab_id).all()
    if not stocks:
        raise HTTPException(status_code=404, detail=f"No stock data found for tab {tab_id}")

    result = []
    for stock in stocks:
        result.append({
            "id": stock.id,
            "tab_id": stock.tab_id,
            "name": stock.name,
            "year_ago": stock.year_ago,
            "current": stock.current,
            "change_percent": stock.change_percent,
            "upload_date": stock.upload_date,
            "data_date": stock.data_date,
            "type": stock.type
        })
    return result
@router.put("/update-data-multiple/")
async def update_multiple_data(
    files: List[UploadFile] = File(...),
    upload_date: date = Form(...),
    data_date: date = Form(...),
    data_type: str = Form(...),
    db: Session = Depends(get_db)
):
    all_updated = []

    for file in files:
        filename = file.filename.lower()
        contents = await file.read()

        # Read Excel/CSV
        try:
            if filename.endswith((".xlsx", ".xls")):
                df = pd.read_excel(io.BytesIO(contents), header=0)
            elif filename.endswith(".csv"):
                df = pd.read_csv(io.StringIO(contents.decode('utf-8')), header=0)
            else:
                raise HTTPException(status_code=400, detail=f"Invalid file type: {filename}")
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Failed to read file {filename}: {e}")

        if df.shape[1] < 5:
            raise HTTPException(status_code=400, detail=f"{filename} must have at least 5 columns")

        # Rename columns
        df.columns = ["name", "year_ago", "current", "change_percent", "tab_id"] + \
                     [f"extra_{i}" for i in range(df.shape[1]-5)]

        # Remove invalid rows
        df = df[df["year_ago"].apply(lambda x: str(x).replace('.', '', 1).isdigit())]

        updated_records = []
        BATCH_SIZE = 20

        # Update tab-wise
        for tab_number, tab_data in df.groupby("tab_id"):
            for _, row in tab_data.iterrows():
                # Find existing record
                stock = db.query(StockData).filter(
                    StockData.name == str(row["name"]),
                    StockData.tab_id == float(row["tab_id"]),
                    StockData.upload_date == upload_date,
                    StockData.data_date == data_date,
                    StockData.type == data_type
                ).first()

                if stock:
                    # Update existing record
                    stock.year_ago = float(row["year_ago"])
                    stock.current = float(row["current"])
                    stock.change_percent = float(row["change_percent"])
                    updated_records.append(stock)
                else:
                    # Insert as new if not found
                    new_stock = StockData(
                        tab_id=float(row["tab_id"]),
                        name=str(row["name"]),
                        year_ago=float(row["year_ago"]),
                        current=float(row["current"]),
                        change_percent=float(row["change_percent"]),
                        upload_date=upload_date,
                        data_date=data_date,
                        type=data_type
                    )
                    db.add(new_stock)
                    updated_records.append(new_stock)

        db.commit()

        all_updated.append({
            "file": filename,
            "records_updated_or_inserted": len(updated_records),
            "tabs": df['tab_id'].nunique()
        })

    return {
        "message": f"Processed {len(files)} files for update.",
        "details": all_updated
    }
    
    
    
@router.delete("/marketindicator/uploads/{upload_id}")
def delete_upload(upload_id: int, db: Session = Depends(get_db)):
    """
    Delete an uploaded file, its DB record, and related stock data
    """
    upload = db.query(MarketIndicatorUpload).filter(
        MarketIndicatorUpload.id == upload_id
    ).first()

    if not upload:
        raise HTTPException(status_code=404, detail="Upload not found")

    # Delete related stock data
    deleted_stocks = db.query(StockData).filter(
        StockData.upload_date == upload.upload_date,
        StockData.data_date == upload.data_date,
        StockData.type == upload.data_type
    ).delete(synchronize_session=False)

    # Delete file from filesystem
    if upload.file_path and os.path.exists(upload.file_path):
        os.remove(upload.file_path)

    # Delete upload record
    db.delete(upload)
    db.commit()

    return {
        "message": "Upload deleted successfully",
        "upload_id": upload_id,
        "stocks_deleted": deleted_stocks
    }
