from sqlalchemy import Column, Integer, Date, String, DECIMAL
from app.database import Base

class IpoTrack(Base):
    __tablename__ = 'ipo_track'

    ID = Column(Integer, primary_key=True,nullable=True)
    INDIC = Column(String(2), nullable=True)
    COCODE = Column(String(6), nullable=True)
    CO_NAME = Column(String(25), nullable=False)

    ISS_OPEN = Column(Date, nullable=True)
    ISS_CLOSE = Column(Date, nullable=True)

    HIGH = Column(DECIMAL(7, 2), nullable=True)
    LOW = Column(DECIMAL(7, 2), nullable=True)
    IPO_PR = Column(DECIMAL(7, 2), nullable=True)
    FV = Column(DECIMAL(7, 2), nullable=True)

    ISS_AMT = Column(DECIMAL(7, 2), nullable=True)
    ISS_QTY = Column(DECIMAL(7, 2), nullable=True)

    LISTED_PR = Column(DECIMAL(7, 2), nullable=True)
    LISTED_GAIN = Column(DECIMAL(7, 2), nullable=True)
    LISTED_DT = Column(Date, nullable=True)

    CMP = Column(DECIMAL(7, 2), nullable=True)
    CUR_GAIN = Column(DECIMAL(7, 2), nullable=True)

    MIN_LOT = Column(Integer, nullable=True)

    EXCH = Column(String(11), nullable=True)
    ISS_TYPE = Column(String(40), nullable=True)

    LM1 = Column(String(100), nullable=True)
    LM2 = Column(String(100), nullable=True)
    LM3 = Column(String(100), nullable=True)
    LM4 = Column(String(100), nullable=True)
    LM5 = Column(String(100), nullable=True)
    LM6 = Column(String(100), nullable=True)
    LM7 = Column(String(100), nullable=True)
    LM8 = Column(String(100), nullable=True)
    LM9 = Column(String(100), nullable=True)
    LM10 = Column(String(100), nullable=True)
    LM11 = Column(String(100), nullable=True)
    LM12 = Column(String(100), nullable=True)
    LM13 = Column(String(100), nullable=True)
    LM14 = Column(String(100), nullable=True)
    LM15 = Column(String(100), nullable=True)

    MKTMKR1 = Column(String(100), nullable=True)
    MKTMKR2 = Column(String(100), nullable=True)
    MKTMKR3 = Column(String(100), nullable=True)
    
class IpoTrackUpload(Base):
    __tablename__ = "ipo_track_upload"

    id = Column(Integer, primary_key=True, index=True)
    mkt_date = Column(Date, nullable=False)
    file_name = Column(String(255), nullable=False)
    file_path = Column(String(500), nullable=False)
