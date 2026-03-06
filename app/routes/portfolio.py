from fastapi import APIRouter, UploadFile, File, HTTPException, Depends
from sqlalchemy.orm import Session
from app.database import SessionLocal
from app.models.portfolio import Stocks_Movements, PortfolioStocs
import pandas as pd
from decimal import Decimal
from pydantic import BaseModel
from datetime import datetime
from typing import List
import math

router = APIRouter(
    prefix="/stocks_movements",
    tags=["Portfolio"]
)

# ------------------------
# Pydantic Schemas
# ------------------------
class PortfolioCreate(BaseModel):
    userid: int
    company: str
    isin: str

class PortfolioResponse(BaseModel):
    id: int
    userid: int
    company: str
    isin: str
    added_at: datetime

    class Config:
        orm_mode = True

class StockMovementSchema(BaseModel):
    company: str
    isin: str
    Day_1: float | None
    Day_2: float | None
    Day_3: float | None
    Day_4: float | None
    Day_5: float | None

    class Config:
        orm_mode = True

# ------------------------
# Database dependency
# ------------------------
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# ------------------------
# Helper: Clean NaN for JSON
# ------------------------
def clean_val(val):
    """Convert None, NaN, or infinite to JSON null."""
    try:
        if val is None:
            return None
        f = float(val)
        if math.isnan(f) or math.isinf(f):
            return None
        return f
    except:
        return None

# ------------------------
# Upload CSV and update stock movements
# ------------------------
@router.post("/upload-stock-csv")
async def upload_stock_csv(file: UploadFile = File(...), db: Session = Depends(get_db)):
    if not file.filename.endswith((".csv", ".txt")):
        raise HTTPException(status_code=400, detail="Invalid file type")

    try:
        content = await file.read()
        df = pd.read_csv(pd.io.common.BytesIO(content), header=None, encoding="ISO-8859-1")
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to read CSV: {e}")

    company_col = 2
    isin_col = 29
    ch_col = 5

    for idx, row in df.iterrows():
        company = str(row[company_col]).strip()
        isin = str(row[isin_col]).strip()
        try:
            ch_val = float(row[ch_col])
            ch = None if math.isnan(ch_val) or math.isinf(ch_val) else round(ch_val, 2)
        except:
            ch = None

        if not company or not isin or ch is None:
            continue

        stock = db.query(Stocks_Movements).filter(Stocks_Movements.isin == isin).first()
        if stock:
            days = [ch, stock.Day_1, stock.Day_2, stock.Day_3, stock.Day_4]
            stock.Day_1, stock.Day_2, stock.Day_3, stock.Day_4, stock.Day_5 = days
        else:
            stock = Stocks_Movements(
                company=company,
                isin=isin,
                Day_1=ch,
                Day_2=None,
                Day_3=None,
                Day_4=None,
                Day_5=None
            )
            db.add(stock)

    db.commit()
    return {"message": "CSV uploaded and stock movements updated successfully"}

# ------------------------
# GET all stock movements
# ------------------------
@router.get("/stocks", response_model=List[StockMovementSchema])
def get_stock_movements(db: Session = Depends(get_db)):
    stocks = db.query(Stocks_Movements).all()
    if not stocks:
        raise HTTPException(status_code=404, detail="No stock movements found")

    result = [
        {
            "company": s.company,
            "isin": s.isin,
            "Day_1": clean_val(s.Day_1),
            "Day_2": clean_val(s.Day_2),
            "Day_3": clean_val(s.Day_3),
            "Day_4": clean_val(s.Day_4),
            "Day_5": clean_val(s.Day_5),
        } for s in stocks
    ]
    return result

# ------------------------
# GET a single stock by ISIN
# ------------------------
@router.get("/stock/{isin}", response_model=StockMovementSchema)
def get_stock_by_isin(isin: str, db: Session = Depends(get_db)):
    stock = db.query(Stocks_Movements).filter(Stocks_Movements.isin == isin).first()
    if not stock:
        raise HTTPException(status_code=404, detail=f"Stock with ISIN {isin} not found")

    return {
        "company": stock.company,
        "isin": stock.isin,
        "Day_1": clean_val(stock.Day_1),
        "Day_2": clean_val(stock.Day_2),
        "Day_3": clean_val(stock.Day_3),
        "Day_4": clean_val(stock.Day_4),
        "Day_5": clean_val(stock.Day_5),
    }

# ------------------------
# Add stock to user portfolio
# ------------------------
@router.post("/portfolio", response_model=PortfolioResponse)
def add_portfolio_stock(data: PortfolioCreate, db: Session = Depends(get_db)):
    existing = db.query(PortfolioStocs).filter(
        PortfolioStocs.userid == data.userid,
        PortfolioStocs.isin == data.isin
    ).first()
    if existing:
        raise HTTPException(status_code=400, detail="Stock already in portfolio")

    stock = PortfolioStocs(
        userid=data.userid,
        company=data.company,
        isin=data.isin,
        added_at=datetime.utcnow()
    )
    db.add(stock)
    db.commit()
    db.refresh(stock)
    return stock

# ------------------------
# Get portfolio for a user
# ------------------------
@router.get("/portfolio/{userid}", response_model=List[PortfolioResponse])
def get_portfolio(userid: int, db: Session = Depends(get_db)):
    return db.query(PortfolioStocs).filter(PortfolioStocs.userid == userid).all()

# ------------------------
# Delete a stock from user portfolio
# ------------------------
@router.delete("/portfolio/{userid}/{isin}")
def delete_portfolio_stock(userid: int, isin: str, db: Session = Depends(get_db)):
    stock = db.query(PortfolioStocs).filter(
        PortfolioStocs.userid == userid,
        PortfolioStocs.isin == isin
    ).first()
    if not stock:
        raise HTTPException(status_code=404, detail=f"Stock with ISIN {isin} not found in user {userid}'s portfolio")
    db.delete(stock)
    db.commit()
    return {"message": f"Stock {isin} removed from user {userid}'s portfolio successfully"}