from sqlalchemy import Column, String, Numeric, Integer, Date
from app.database import Base

class McapGainersLosers(Base):
    __tablename__ = "mcap_gainers_losers"

    COMPANY = Column(String(25), nullable=True)
    ISIN = Column(String(25), primary_key=True, index=True)
    CMP = Column(Numeric(20, 2), nullable=False)
    MCAP_CR = Column(Numeric(20, 2), nullable=False)
    CH_CR = Column(Numeric(20, 2), nullable=False)
    CH_PER = Column(Numeric(20, 2), nullable=False)
    VOL_NOS = Column(Integer, nullable=False)
    VOL_CH_PER = Column(Numeric(20, 1), nullable=False)
    DAY_HIGH = Column(Numeric(20, 2), nullable=False)
    DAY_LOW = Column(Numeric(20, 2), nullable=False)
    DMA_60 = Column("60DMA", Numeric(20, 2), nullable=False)
    DMA_PER_60 = Column("60DMA_PER", Numeric(20, 2), nullable=False)
    DMA_245 = Column("245DMA", Numeric(20, 2), nullable=False)
    DMA_PER_245 = Column("245DMA_PER", Numeric(20, 2), nullable=False)
    WKH_52 = Column("52WKH", Numeric(20, 2), nullable=False)
    WKL_52 = Column("52WKL", Numeric(20, 2), nullable=False)
    group_id = Column(String(36), nullable=False, index=True)  # Added group_id

class McapGainersLosersUpload(Base):
    __tablename__ = "mcap_gainers_losers_upload"

    id = Column(Integer, primary_key=True, index=True)
    group_id = Column(String(36), index=True, nullable=False)
    upload_date = Column(Date, nullable=False)
    data_date = Column(Date, nullable=False)
    category = Column(String(100), nullable=False)
    file_name = Column(String(255), nullable=False)
    file_path = Column(String(500), nullable=False)
    
class Upward_DownwardMobile(Base):
    __tablename__ = "upward_downward_mobile"

    COMPANY = Column(String(25), nullable=True)
    ISIN = Column(String(25), primary_key=True, index=True)
    CMP = Column(Numeric(20, 2), nullable=False)
    START= Column(Numeric(20, 2), nullable=False)
    DAYS = Column(Integer(), nullable=False)
    CH_PER = Column(Numeric(20, 2), nullable=False)
    PERDAY = Column(Numeric(20, 2), nullable=False)
    group_id = Column(String(36), nullable=False, index=True)  # Added group_id

class Upward_DownwardMobileUpload(Base):
    __tablename__ = "upward_downward_mobile_upload"

    id = Column(Integer, primary_key=True, index=True)
    group_id = Column(String(36), index=True, nullable=False)
    upload_date = Column(Date, nullable=False)
    data_date = Column(Date, nullable=False)
    category = Column(String(100), nullable=False)
    file_name = Column(String(255), nullable=False)
    file_path = Column(String(500), nullable=False)

class Up_DownTrend(Base):
    __tablename__ = "up_down_trend"

    COMPANY = Column(String(25), nullable=True)
    ISIN = Column(String(25), primary_key=True, index=True)
    CMP = Column(Numeric(20, 2), nullable=False)
    DMA_5= Column("5DMA", Numeric(20, 2), nullable=False)
    DMA_21 = Column("21DMA", Numeric(20, 2), nullable=False)
    DMA_60 = Column("60DMA", Numeric(20, 2), nullable=False)
    DMA_245 = Column("245DMA", Numeric(20, 2), nullable=False)
    CH_PER= Column(Numeric(20, 1), nullable=False)
    group_id = Column(String(36), nullable=False, index=True)  # Added group_id

class Up_DownTrendUpload(Base):
    __tablename__ = "up_down_trend_upload"

    id = Column(Integer, primary_key=True, index=True)
    group_id = Column(String(36), index=True, nullable=False)
    upload_date = Column(Date, nullable=False)
    data_date = Column(Date, nullable=False)
    category = Column(String(100), nullable=False)
    file_name = Column(String(255), nullable=False)
    file_path = Column(String(500), nullable=False)
        