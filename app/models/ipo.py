from sqlalchemy import Column, Integer, String, Float, Date
from app.database import Base

class DataUpload(Base):
    __tablename__ = "ipo_data"

    id = Column(Integer, primary_key=True, index=True)
    upload_date = Column(Date, nullable=False)
    data_date = Column(Date, nullable=False)

    isin = Column(String, index=True, nullable=True)
    co_name = Column(String, nullable=True)
    ibr_name = Column(String, nullable=True)
    iss_open = Column(Date, nullable=True)
    iss_close = Column(Date, nullable=True)
    allotment_date = Column(Date, nullable=True)
    refund_dt = Column(Date, nullable=True)
    demat_dt = Column(Date, nullable=True)
    trading_dt = Column(Date, nullable=True)
    high = Column(Float, nullable=True)
    low = Column(Float, nullable=True)
    off_price = Column(Float, nullable=True)
    face_value = Column(Float, nullable=True)
    iss_amt = Column(Float, nullable=True)
    iss_qty = Column(Float, nullable=True)
    listed_pr = Column(Float, nullable=True)
    listed_gain = Column(Float, nullable=True)
    listed_dt = Column(Date, nullable=True)
    mkt_lot = Column(Float, nullable=True)
    subs_times = Column(Float, nullable=True)
    exch = Column(String, nullable=True)
    iss_type = Column(String, nullable=True)
    offer_type = Column(String, nullable=True)
    offer_objective = Column(String, nullable=True)
    state = Column(String, nullable=True)
    signed_by = Column(String, nullable=True)
    industry = Column(String, nullable=True)
    lm1 = Column(String, nullable=True)
    lm2 = Column(String, nullable=True)
    lm3 = Column(String, nullable=True)
    lm4 = Column(String, nullable=True)
    lm5 = Column(String, nullable=True)
    lm6 = Column(String, nullable=True)
    lm7 = Column(String, nullable=True)
    lm8 = Column(String, nullable=True)
    lm9 = Column(String, nullable=True)
    lm10 = Column(String, nullable=True)
    lm11 = Column(String, nullable=True)
    lm12 = Column(String, nullable=True)
    lm13 = Column(String, nullable=True)
    lm14 = Column(String, nullable=True)
    lm15 = Column(String, nullable=True)
    mktmkr1 = Column(String, nullable=True)
    mktmkr2 = Column(String, nullable=True)
    mktmkr3 = Column(String, nullable=True)
    mktmkr4 = Column(String, nullable=True)
    mktmkr5 = Column(String, nullable=True)
class IPOUpload(Base):
    __tablename__ = "ipo_upload"

    id = Column(Integer, primary_key=True, index=True)

    upload_date = Column(Date, nullable=False)
    data_date = Column(Date, nullable=False)
    data_type = Column(String(100), nullable=False)

    file_name = Column(String(255), nullable=False)
    file_path = Column(String(500), nullable=False)  # stored path or URL
    file_path = Column(String, nullable=False)  # actual path on disk
    