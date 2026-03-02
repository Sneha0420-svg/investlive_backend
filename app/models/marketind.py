from sqlalchemy import Column, Integer, String, Float, Date, Numeric
from app.database import Base  

class StockData(Base):
    __tablename__ = "mkt_tbl"

    unique_id = Column(Integer, primary_key=True, index=True)
    name = Column(String(25), nullable=False)
    yr_ago = Column(Numeric(20, 2), nullable=True)
    curnt = Column(Numeric(20, 2), nullable=True)
    ch = Column(Numeric(20, 1), nullable=True)
    H_ID = Column(Integer, nullable=False)
    S_ID = Column(Integer, nullable=False)
    IDX_ID = Column(Integer, nullable=False)
    flag = Column(String(10), nullable=False)
    ID=Column(Integer,nullable=True)
    mkt_date = Column(Date, nullable=True) 

class MarketIndicatorUpload(Base):
    __tablename__ = "market_indicator_uploads"

    id = Column(Integer, primary_key=True, index=True)

    mkt_date = Column(Date, nullable=False)

    file_name = Column(String(255), nullable=False)
    file_path = Column(String(500), nullable=False)  # stored path or URL   
