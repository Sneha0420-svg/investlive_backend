from sqlalchemy import Column, Integer, String, Date
from app.database import Base

class StockTrack(Base):
    __tablename__ = "stock_track"

    id = Column("ID", Integer, primary_key=True, index=True)
    mkt_date = Column(Date, nullable=True)
    isin = Column("ISIN", String(12), nullable=False)

    # adjust lengths based on real CSV data
    wk52 = Column("WK52", String(12), nullable=False)
    multi_yr = Column("MULTI_YR", String(5), nullable=False)
    circuit = Column("CIRCUIT", String(5), nullable=False)
    mobility = Column("MOBILITY", String(5), nullable=False)
    trend = Column("TREND", String(5), nullable=False)

    wk_bust = Column("WK_BUST", String(5), nullable=False)
    mth_bust = Column("MTH_BUST", String(5), nullable=False)
    qtr_bust = Column("QTR_BUST", String(5), nullable=False)
    yr_bust = Column("YR_BUST", String(5), nullable=False)


class StockTrackUpload(Base):
    __tablename__ = "stock_track_uploads"

    id = Column(Integer, primary_key=True, index=True)

    mkt_date = Column(Date, nullable=False)

    file_name = Column(String(255), nullable=False)
    file_path = Column(String(500), nullable=False)  # stored path or URL   

