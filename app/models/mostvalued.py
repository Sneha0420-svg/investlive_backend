from sqlalchemy import Column, Integer, String, Float, Date
from app.database import Base

class MostValuedHouses(Base):
    __tablename__ = "most_valued_houses"

    id = Column(Integer, primary_key=True, index=True)

    house = Column(String(45), nullable=False)

    today = Column(Float)
    p_day = Column(Float)
    p_wk = Column(Float)
    p_mth = Column(Float)
    p_qtr = Column(Float)
    p_hy = Column(Float)
    p_yr = Column(Float)
    
class MostValuedStock(Base):
    __tablename__ = "most_valued_stock"

    id = Column(Integer, primary_key=True, index=True)

    company = Column(String(25), nullable=False)
    isin = Column(String(25), nullable=False)

    today = Column(Float)
    p_day = Column(Float)
    p_wk = Column(Float)
    p_mth = Column(Float)
    p_qtr = Column(Float)
    p_hy = Column(Float)
    p_yr = Column(Float)


class MostValuedHousesUpload(Base):
    __tablename__ = "most_valued_houses_uploads"

    id = Column(Integer, primary_key=True, index=True)

    upload_date = Column(Date, nullable=False)
    data_date = Column(Date, nullable=False)

    file_name = Column(String(255), nullable=False)
    file_path = Column(String(500), nullable=False)
    
class MostValuedStockUpload(Base):
    __tablename__ = "most_valued_stock_uploads"

    id = Column(Integer, primary_key=True, index=True)

    upload_date = Column(Date, nullable=False)
    data_date = Column(Date, nullable=False)

    file_name = Column(String(255), nullable=False)
    file_path = Column(String(500), nullable=False)