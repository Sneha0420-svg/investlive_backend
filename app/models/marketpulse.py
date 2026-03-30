from sqlalchemy import Column, String, BigInteger, Date, Integer,BigInteger

from app.database import Base

class StockPulseTable(Base):
    __tablename__ = "stockpulse_tbl"
    ID = Column(Integer, primary_key=True, index=True, autoincrement=True)
    TYPE = Column(String(20),nullable=True)

    MCAP = Column(BigInteger, nullable=False)

    DMA_5 = Column(BigInteger, nullable=False)
    DMA_21 = Column(BigInteger, nullable=False)
    DMA_60 = Column(BigInteger, nullable=False)
    DMA_245 = Column(BigInteger, nullable=False)

    WK52H_MCAP = Column(BigInteger, nullable=False)
    WK52HDT = Column(String(15), nullable=False)

    WK52L_MCAP = Column(BigInteger, nullable=False)
    WK52LDT = Column(String(15), nullable=False)

    VOL = Column(String(15), nullable=False)

    DVMA_5 = Column(String(15), nullable=False)
    DVMA_21 = Column(String(15), nullable=False)
    DVMA_60 = Column(String(15), nullable=False)
    DVMA_245 = Column(String(15), nullable=False)

    WK52H_VOL = Column(String(15), nullable=False)
    WK52HVDT = Column(String(15), nullable=False)

    WK52L_VOL = Column(String(15), nullable=False)
    WK52LVDT = Column(String(15), nullable=False)

class StockPulseTableUpload(Base):
    __tablename__ = "stockpulse_tbl_upload"

    id = Column(Integer, primary_key=True, index=True)
    mrk_date = Column(Date, nullable=False)
    data_type = Column(String(100), nullable=False) 
    file_name = Column(String(255), nullable=False)
    file_path = Column(String(500), nullable=False)
class StockPulseIndex(Base):
    __tablename__ = "stockpulse_index"

    ID = Column(Integer, primary_key=True, index=True, autoincrement=True)

    TYPE = Column(String(25), nullable=False)
    TRN_DATE = Column(Date, nullable=False, index=True)

    MCAP = Column(BigInteger, nullable=False)
    FFLT = Column(BigInteger, nullable=False)

    DMA_5 = Column(BigInteger, nullable=False)
    DMA_21 = Column(BigInteger, nullable=False)
    DMA_60 = Column(BigInteger, nullable=False)
    DMA_245 = Column(BigInteger, nullable=False)

    STOCKS = Column(Integer, nullable=False)
    ADV = Column(Integer, nullable=False)
    DEC = Column(Integer, nullable=False)
    UNCHG = Column(Integer, nullable=False)

    VOL = Column(BigInteger, nullable=False)
    
class StockPulseIndexUpload(Base):
    __tablename__ = "stockpulse_index_upload"

    id = Column(Integer, primary_key=True, index=True)
    mrk_date = Column(Date, nullable=False)
    data_type = Column(String(100), nullable=False) 
    file_name = Column(String(255), nullable=False)
    file_path = Column(String(500), nullable=False)