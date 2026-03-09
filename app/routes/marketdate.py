from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.database import SessionLocal
from app.models.marketdate import MarketDate
from app.schemas.marketdate import MarketDateCreate

router = APIRouter(prefix="/market-date", tags=["Market Date"])

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
# CREATE (delete old date and insert new one)
@router.post("/")
def create_market_date(data: MarketDateCreate, db: Session = Depends(get_db)):

    # delete old date
    db.query(MarketDate).delete()

    # insert new date
    new_date = MarketDate(mkt_date=data.mkt_date)
    db.add(new_date)
    db.commit()
    db.refresh(new_date)

    return new_date


# GET market date
@router.get("/")
def get_market_date(db: Session = Depends(get_db)):
    return db.query(MarketDate).first()