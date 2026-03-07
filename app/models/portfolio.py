from sqlalchemy import Column, Integer, String, Text, DateTime,Numeric,Date
from app.database import Base
from datetime import datetime


class Stocks_Movements(Base):
    __tablename__ = "stocks_movements"

    id = Column(Integer, primary_key=True, index=True)
    company = Column(String(255), nullable=False)
    isin=Column(String,nullable=False)
    Day_1=Column(Numeric(20, 1), nullable=True)
    Day_2=Column(Numeric(20, 1), nullable=True)
    Day_3=Column(Numeric(20, 1), nullable=True)
    Day_4=Column(Numeric(20, 1), nullable=True)
    Day_5=Column(Numeric(20, 1), nullable=True)
    
class PortfolioStocs(Base):
    
    __tablename__="portfolio_stocks"
    
    id = Column(Integer, primary_key=True, index=True)
    userid = Column(Integer,nullable=False)
    company = Column(String(255), nullable=False)
    isin=Column(String,nullable=False)
    added_at=Column(DateTime, default=datetime.utcnow, nullable=False)

class Stock_MovementsUploadHistory(Base):
    __tablename__ = "stocks_movements_history"

    id = Column(Integer, primary_key=True, index=True)
   
    file_name = Column(String)
    file_path = Column(String(500), nullable=False)
    mkt_date = Column(Date, nullable=False)
    uploaded_at = Column(DateTime, default=datetime.utcnow)
    

    