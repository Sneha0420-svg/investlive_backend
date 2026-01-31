# app/models/stockpulse.py
from sqlalchemy import Column, Integer, String, Float, Date
from app.database import Base


class StockPulseUpload(Base):
    __tablename__ = "stockpulse_upload"

    id = Column(Integer, primary_key=True, index=True)
    upload_date = Column(Date, nullable=True)
    data_date = Column(Date, nullable=True)
    data_type = Column(String, nullable=True)
    file_name = Column(String, nullable=True)
    file_path = Column(String, nullable=True)


class StockPulseData(Base):
    __tablename__ = "stockpulse"

    id = Column(Integer, primary_key=True, index=True)
    scrip_code = Column(String, nullable=True)
    scrip = Column(String, nullable=True)
    co_code = Column(String, nullable=True)
    isin = Column(String, nullable=True)
    fv = Column(Float, nullable=True)
    cmp = Column(Float, nullable=True)

    dma_5 = Column(Float, nullable=True)
    dma_21 = Column(Float, nullable=True)
    dma_60 = Column(Float, nullable=True)
    dma_245 = Column(Float, nullable=True)

    wkh_52 = Column(Float, nullable=True)
    wkhdt_52 = Column(Date, nullable=True)
    wkl_52 = Column(Float, nullable=True)
    wkldt_52 = Column(Date, nullable=True)

    cur_vol = Column(Float, nullable=True)

    dvma_5 = Column(Float, nullable=True)
    dvma_21 = Column(Float, nullable=True)
    dvma_60 = Column(Float, nullable=True)
    dvma_245 = Column(Float, nullable=True)

    wkhv_52 = Column(Float, nullable=True)
    wkhvdt_52 = Column(Date, nullable=True)
    wklv_52 = Column(Float, nullable=True)
    wklvdt_52 = Column(Date, nullable=True)

    myrh = Column(Float, nullable=True)
    myrhdt = Column(Date, nullable=True)
    myrl = Column(Float, nullable=True)
    myrldt = Column(Date, nullable=True)
    myruh = Column(Float, nullable=True)
    myruhdt = Column(Date, nullable=True)
    myrul = Column(Float, nullable=True)
    myruldt = Column(Date, nullable=True)
    pulse_score=Column(Integer)

    data_date = Column(Date, nullable=True)
    type = Column(String, nullable=True)
