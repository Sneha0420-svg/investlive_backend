from sqlalchemy import Column, Integer, String, Float, Date
from app.database import Base  

class StockData(Base):
    __tablename__ = "stock_data"

    id = Column(Integer, primary_key=True, index=True)
    tab_id = Column(Float, nullable=False)
    name = Column(String, index=True)
    year_ago = Column(Float)
    current = Column(Float)
    change_percent = Column(Float)
    upload_date = Column(Date, nullable=False)  # new
    data_date = Column(Date, nullable=False)    # new
    type = Column(String, nullable=False)

class MarketIndicatorUpload(Base):
    __tablename__ = "market_indicator_uploads"

    id = Column(Integer, primary_key=True, index=True)

    upload_date = Column(Date, nullable=False)
    data_date = Column(Date, nullable=False)
    data_type = Column(String(100), nullable=False)

    file_name = Column(String(255), nullable=False)
    file_path = Column(String(500), nullable=False)  # stored path or URL   
