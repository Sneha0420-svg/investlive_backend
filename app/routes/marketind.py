from fastapi import APIRouter, Depends, UploadFile, File, HTTPException, Form
from sqlalchemy import func
from sqlalchemy.orm import Session
from fastapi.responses import FileResponse
from app.models.marketind import StockData, MarketIndicatorUpload
from app.database import SessionLocal
import pandas as pd
import io, os, math
from datetime import date
from typing import List, Dict, Any
from app.schemas.marketind import LatestStocksResponse
UPLOAD_FOLDER = "uploads"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

router = APIRouter(tags=["Market Indicator"])

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def safe_int(value, default=0):
    """Convert value to int safely, treating NaN/None as default."""
    try:
        if value is None or (isinstance(value, float) and math.isnan(value)):
            return default
        return int(value)
    except Exception:
        return default


def safe_float(value, default=0.0):
    """Convert value to float safely, treating NaN/None as default."""
    try:
        if value is None or (isinstance(value, float) and math.isnan(value)):
            return default
        return float(value)
    except Exception:
        return default


@router.post("/upload-data-multiple/")
async def upload_multiple_data(
    files: List[UploadFile] = File(...),
    mkt_date: date = Form(...),
    db: Session = Depends(get_db)
):
    """
    Upload multiple CSV/XLSX files for StockData.
    Deletes existing data for the same mkt_date before inserting new data.
    """
    all_inserted = []

    # Step 0: Delete existing data for the incoming mkt_date
    existing_count = db.query(StockData).filter(StockData.mkt_date == mkt_date).delete(synchronize_session=False)
    db.commit()

    for file in files:
        filename = file.filename
        file_path = os.path.join(UPLOAD_FOLDER, filename)

        # Save file to disk
        with open(file_path, "wb") as f:
            f.write(await file.read())

        # Save info to MarketIndicatorUpload table
        upload_record = MarketIndicatorUpload(
            mkt_date=mkt_date,
            file_name=filename,
            file_path=file_path
        )
        db.add(upload_record)
        db.commit()
        db.refresh(upload_record)

        # Read CSV/XLSX
        with open(file_path, "rb") as f:
            contents = f.read()
        try:
            if filename.endswith((".xlsx", ".xls")):
                df = pd.read_excel(io.BytesIO(contents), header=None)
            elif filename.endswith(".csv"):
                df = pd.read_csv(io.StringIO(contents.decode("utf-8")), header=None)
            else:
                raise HTTPException(status_code=400, detail=f"Invalid file type: {filename}")
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Failed to read file {filename}: {e}")

        # Ensure minimum columns
        if df.shape[1] < 9:
            raise HTTPException(status_code=400, detail=f"{filename} must have at least 9 columns")

        # Rename columns
        df.columns = ["name", "yr_ago", "curnt", "ch", "H_ID", "S_ID", "IDX_ID", "flag", "ID"]

        inserted_records = []
        BATCH_SIZE = 20

        # Insert stock data
        for tab_number, tab_data in df.groupby("H_ID"):
            objects = []
            for _, row in tab_data.iterrows():
                stock = StockData(
                    name=str(row["name"]).strip() if row["name"] else "",
                    yr_ago=safe_float(row["yr_ago"]),
                    curnt=safe_float(row["curnt"]),
                    ch=safe_float(row["ch"]),
                    H_ID=safe_int(row["H_ID"]),
                    S_ID=safe_int(row["S_ID"]),
                    IDX_ID=safe_int(row["IDX_ID"]),
                    flag=str(row["flag"]).strip() if row["flag"] else "",
                    ID=safe_int(row.get("ID")),
                    mkt_date=mkt_date
                )
                objects.append(stock)
                inserted_records.append(stock)

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
            "tabs": df['H_ID'].nunique(),
            "upload_id": upload_record.id,
            "file_link": f"/files/{upload_record.id}"
        })

    return {
        "message": f"Processed {len(files)} files successfully. "
                   f"Existing rows for {mkt_date} deleted: {existing_count}",
        "details": all_inserted
    }
# --------------------- Get All Uploads ---------------------
@router.get("/marketindicator/uploads/", response_model=List[dict])
def get_uploads(db: Session = Depends(get_db)):
    uploads = db.query(MarketIndicatorUpload).order_by(MarketIndicatorUpload.mkt_date.desc()).all()
    if not uploads:
        raise HTTPException(status_code=404, detail="No uploads found")

    return [
        {
            "id": upload.id,
            "mkt_date": upload.mkt_date,
            "file_name": upload.file_name,
            "file_link": f"/files/{upload.id}"
        } for upload in uploads
    ]


# --------------------- Download File ---------------------
@router.get("/files/{upload_id}")
def download_file(upload_id: int, db: Session = Depends(get_db)):
    record = db.query(MarketIndicatorUpload).filter(MarketIndicatorUpload.id == upload_id).first()
    if not record:
        raise HTTPException(status_code=404, detail="File not found")

    if not os.path.exists(record.file_path):
        raise HTTPException(status_code=404, detail="File not found on server")

    return FileResponse(path=record.file_path, filename=record.file_name, media_type='application/octet-stream')


# --------------------- Get All Stocks by Latest Mkt Date ---------------------
def is_header_row(stock: StockData) -> bool:
    """Detect if a stock row is a header: all numeric columns are None or 0."""
    numeric_fields = [stock.yr_ago, stock.curnt, stock.ch,stock.S_ID,stock.IDX_ID]
    return all(f is None or f == 0 for f in numeric_fields)

@router.get("/marketindicator/latest/", response_model=Dict[str, Any])
def get_latest_marketindicator(db: Session = Depends(get_db)):
    """
    Fetch latest market indicator data grouped by tab and sections.
    """
    # Step 1: Get latest mkt_date
    latest_date = db.query(func.max(StockData.mkt_date)).scalar()
    if not latest_date:
        raise HTTPException(status_code=404, detail="No stock data found")

    # Step 2: Fetch all stock data for that date
    stocks = db.query(StockData).filter(StockData.mkt_date == latest_date)\
        .order_by(StockData.H_ID, StockData.ID).all()

    if not stocks:
        raise HTTPException(status_code=404, detail=f"No stock data found for latest mkt_date: {latest_date}")

    # Step 3: Tab mapping
    tab_map = {
        1: "Returns",
        2: "Indices",
        3: "Currencies",
        4: "World P/E Ratio",
        5: "Commodities"
    }

    # Step 4: Section headers for each tab
    tab_sections = {
        1: ["India Stocks", "Bullion", "Forex vs INR", "Crude"],
        2: ["BRICS", "Asia/Pacific", "America/Europe"],
        3: ["INR vs.", "USD vs."],
        5: ["Metals (Kg)", "Agro-Indu (100 Kg)"]
    }

    # Step 5: Prepare result structure
    result = {tab_name: [] for tab_name in tab_map.values()}
    current_section_per_tab = {}

    for stock in stocks:
        tab_name = tab_map.get(stock.H_ID, "Unknown")
        stock_name = (stock.name or "").strip()
        sections_for_tab = tab_sections.get(stock.H_ID, [])

        # Determine if the row is a section header
        is_header = stock_name in sections_for_tab or is_header_row(stock)

        if is_header:
            section_title = stock_name if stock_name in sections_for_tab else "yr-ago"
            section = {"title": section_title, "rows": []}
            result[tab_name].append(section)
            current_section_per_tab[tab_name] = section
        else:
            current_section = current_section_per_tab.get(tab_name)
            if not current_section:
                current_section = {"title": "(No Title)", "rows": []}
                result[tab_name].append(current_section)
                current_section_per_tab[tab_name] = current_section

            # Append the stock data row
            current_section["rows"].append([
                stock.name,
                stock.yr_ago,
                stock.curnt,
                stock.ch
            ])

    # Step 6: Return structured response
    return {
        "latest_mkt_date": latest_date,
        "total_records": len(stocks),
        "stocks_by_tab": result
    }
# --------------------- Get Stocks by IDX_ID ---------------------
@router.get("/marketindicator/idx/{idx_id}", response_model=List[dict])
def get_stocks_by_idx(idx_id: int, db: Session = Depends(get_db)):
    """
    Fetch all stocks for a specific IDX_ID, but only for the latest mkt_date.
    """
    # Step 1: Get the latest mkt_date for this IDX_ID
    latest_date = db.query(func.max(StockData.mkt_date)).filter(StockData.IDX_ID == idx_id).scalar()
    if not latest_date:
        raise HTTPException(status_code=404, detail=f"No stock data found for IDX_ID: {idx_id}")

    # Step 2: Fetch only the stocks for that latest date
    stocks = db.query(StockData).filter(
        StockData.IDX_ID == idx_id,
        StockData.mkt_date == latest_date
    ).order_by(StockData.H_ID, StockData.ID).all()

    if not stocks:
        raise HTTPException(status_code=404, detail=f"No stock data found for IDX_ID: {idx_id} on latest mkt_date: {latest_date}")

    return [
        {
            "id": stock.ID,
            "name": stock.name,
            "yr_ago": stock.yr_ago,
            "curnt": stock.curnt,
            "ch": stock.ch,
            "H_ID": stock.H_ID,
            "S_ID": stock.S_ID,
            "IDX_ID": stock.IDX_ID,
            "flag": stock.flag,
            "mkt_date": stock.mkt_date
        } for stock in stocks
    ]
# --------------------- Delete Upload ---------------------
@router.delete("/marketindicator/uploads/{upload_id}")
def delete_upload(upload_id: int, db: Session = Depends(get_db)):
    upload = db.query(MarketIndicatorUpload).filter(MarketIndicatorUpload.id == upload_id).first()
    if not upload:
        raise HTTPException(status_code=404, detail="Upload not found")

    deleted_stocks = db.query(StockData).filter(StockData.mkt_date == upload.mkt_date).delete(synchronize_session=False)

    if upload.file_path and os.path.exists(upload.file_path):
        os.remove(upload.file_path)

    db.delete(upload)
    db.commit()

    return {
        "message": "Upload deleted successfully",
        "upload_id": upload_id,
        "stocks_deleted": deleted_stocks
    }