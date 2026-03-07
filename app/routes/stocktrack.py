from fastapi import APIRouter, UploadFile, File, Depends, HTTPException
from sqlalchemy.orm import Session
import shutil
import os
import csv
from datetime import datetime

from app.database import SessionLocal
from app.models.stocktrack import StockTrack, StockTrackUpload

router = APIRouter(prefix="/stocktrack", tags=["Stock Track"])

UPLOAD_DIR = "uploads/stocktrack"

# -------------------- DB DEP --------------------
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# -------------------- Upload CSV Endpoint --------------------
@router.post("/upload-csv")
async def upload_stocktrack_csv(
    mkt_date: str,
    file: UploadFile = File(...),
    db: Session = Depends(get_db)
):
    try:
        os.makedirs(UPLOAD_DIR, exist_ok=True)
        file_path = os.path.join(UPLOAD_DIR, file.filename)

        # save uploaded file
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)

        # convert mkt_date string to date object
        mkt_date_obj = datetime.strptime(mkt_date, "%Y-%m-%d").date()

        # ------------------ DELETE ALL EXISTING DATA ------------------
        db.query(StockTrack).delete()
        db.commit()  # commit deletion before inserting new rows

        # ------------------ READ CSV ------------------
        headers = ["ID","ISIN", "WK52", "MULTI_YR", "CIRCUIT", "MOBILITY", "TREND",
                   "WK_BUST", "MTH_BUST", "QTR_BUST", "YR_BUST"]

        with open(file_path, newline='', encoding="utf-8") as csvfile:
            reader = csv.DictReader(csvfile, fieldnames=headers)

            for row in reader:
                if not row["ISIN"]:  # skip empty rows
                    continue

                stock = StockTrack(
                    mkt_date=mkt_date_obj,
                    isin=row["ISIN"].strip(),
                    wk52=row["WK52"].strip() if row["WK52"] else "N",
                    multi_yr=row["MULTI_YR"].strip() if row["MULTI_YR"] else "N",
                    circuit=row["CIRCUIT"].strip() if row["CIRCUIT"] else "N",
                    mobility=row["MOBILITY"].strip() if row["MOBILITY"] else "N",
                    trend=row["TREND"].strip() if row["TREND"] else "N",
                    wk_bust=row["WK_BUST"].strip() if row["WK_BUST"] else "N",
                    mth_bust=row["MTH_BUST"].strip() if row["MTH_BUST"] else "N",
                    qtr_bust=row["QTR_BUST"].strip() if row["QTR_BUST"] else "N",
                    yr_bust=row["YR_BUST"].strip() if row["YR_BUST"] else "N",
                )
                db.add(stock)

        # ------------------ SAVE UPLOAD RECORD ------------------
        upload_record = StockTrackUpload(
            mkt_date=mkt_date_obj,
            file_name=file.filename,
            file_path=file_path
        )
        db.add(upload_record)
        db.commit()

        return {"message": "Stock Track CSV uploaded and table replaced successfully"}

    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    
# -------------------- Get all uploads --------------------
@router.get("/uploads")
def get_all_uploads(db: Session = Depends(get_db)):
    try:
        uploads = db.query(StockTrackUpload).order_by(StockTrackUpload.mkt_date.desc()).all()
        return [{"id": u.id, "mkt_date": u.mkt_date, "file_name": u.file_name, "file_path": u.file_path.replace("\\","/")} for u in uploads]
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# -------------------- Get all stocks --------------------
@router.get("/stocks")
def get_all_stocks(db: Session = Depends(get_db)):
    try:
        stocks = db.query(StockTrack).order_by(StockTrack.id).all()
        return [
            {
                "id": s.id,
                "mkt_date": s.mkt_date,
                "isin": s.isin,
                "wk52": s.wk52,
                "multi_yr": s.multi_yr,
                "circuit": s.circuit,
                "mobility": s.mobility,
                "trend": s.trend,
                "wk_bust": s.wk_bust,
                "mth_bust": s.mth_bust,
                "qtr_bust": s.qtr_bust,
                "yr_bust": s.yr_bust
            }
            for s in stocks
        ]
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# -------------------- Get stock by ISIN --------------------
@router.get("/stocks/{isin}")
def get_stock_by_isin(isin: str, db: Session = Depends(get_db)):
    try:
        stock = db.query(StockTrack).filter(StockTrack.isin == isin).first()
        if not stock:
            raise HTTPException(status_code=404, detail="Stock not found")
        return {
            "id": stock.id,
            "mkt_date": stock.mkt_date,
            "isin": stock.isin,
            "wk52": stock.wk52,
            "multi_yr": stock.multi_yr,
            "circuit": stock.circuit,
            "mobility": stock.mobility,
            "trend": stock.trend,
            "wk_bust": stock.wk_bust,
            "mth_bust": stock.mth_bust,
            "qtr_bust": stock.qtr_bust,
            "yr_bust": stock.yr_bust
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    
# -------------------- Delete an uploaded CSV --------------------
@router.delete("/uploads/{upload_id}")
def delete_upload(upload_id: int, db: Session = Depends(get_db)):
    try:
        # fetch the upload record
        upload_record = db.query(StockTrackUpload).filter(StockTrackUpload.id == upload_id).first()
        if not upload_record:
            raise HTTPException(status_code=404, detail="Upload not found")

        # delete related stock records for the same mkt_date
        db.query(StockTrack).filter(StockTrack.mkt_date == upload_record.mkt_date).delete()

        # delete the upload record itself
        db.delete(upload_record)
        db.commit()

        # optionally, remove the file from disk
        if os.path.exists(upload_record.file_path):
            os.remove(upload_record.file_path)

        return {"message": f"Upload {upload_id} and its stocks deleted successfully"}

    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))