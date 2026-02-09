from sqlalchemy import Column, String, Numeric, Integer, Date
from app.database import Base

class FiftyTwoWeekHighLow(Base):
    __tablename__ = "52_wk_high_low"

    ISIN = Column(String(25), primary_key=True, index=True)
    COMPANY = Column(String(25), nullable=True)

    CMP = Column(Numeric(20, 2), nullable=False)
    WKH_52 = Column("52WKH", Numeric(20, 2), nullable=False)
    WKL_52 = Column("52WKL", Numeric(20, 2), nullable=False)

    CH_RS = Column(Numeric(20, 2), nullable=False)
    CH_PER = Column(Numeric(20, 2), nullable=False)

    group_id = Column(String(36), nullable=False, index=True)  # Added group_id


class FiftyTwoWeekHighLowUpload(Base):
    __tablename__ = "52_week_high_low_upload"

    id = Column(Integer, primary_key=True, index=True)
    group_id = Column(String(36), index=True, nullable=False)
    upload_date = Column(Date, nullable=False)
    data_date = Column(Date, nullable=False)
    category = Column(String(100), nullable=False)
    file_name = Column(String(255), nullable=False)
    file_path = Column(String(500), nullable=False)


class MultiYearHighLow(Base):
    __tablename__ = "multi_yr_high_low"

    ISIN = Column(String(25), primary_key=True, index=True)
    COMPANY = Column(String(25), nullable=True)
    MCAP = Column(Numeric(20, 2), nullable=False)
    CMP = Column(Numeric(20, 2), nullable=False)
    MYRH = Column(Numeric(20, 2), nullable=False)
    MYRH_DT = Column(String(20), nullable=False)
    MYRL = Column(Numeric(20, 2), nullable=False)
    MYRL_DT = Column(String(20), nullable=False)
    SINCE = Column(String(20), nullable=False)
    TYPE = Column(Integer, nullable=False)
    ID = Column(Integer, primary_key=True)  # Already present
    group_id = Column(String(36), nullable=False, index=True)  # Added group_id


class MultiYearHighLowUpload(Base):
    __tablename__ = "multi_year_high_low_upload"

    id = Column(Integer, primary_key=True, index=True)
    group_id = Column(String(36), index=True, nullable=False)
    upload_date = Column(Date, nullable=False)
    data_date = Column(Date, nullable=False)
    category = Column(String(100), nullable=False)
    file_name = Column(String(255), nullable=False)
    file_path = Column(String(500), nullable=False)

class CircuitUpLow(Base):
    __tablename__ = "circuit_up_low"

    COMPANY = Column(String(25), nullable=True)
    ISIN = Column(String(25), primary_key=True, index=True)
    CMP = Column(Numeric(20, 2), nullable=False)
    CH_PER = Column(Numeric(20, 2), nullable=False)
    VOL = Column(Integer, nullable=False)
    VALUE = Column(Integer, nullable=False)
    TRADE = Column(Integer, nullable=False)
    WKH_52 = Column("52WKH", Numeric(20, 2), nullable=False)
    WKH_DT_52 = Column("52WKHDT", String(11), nullable=False)
    WKL_52 = Column("52WKL", Numeric(20, 2), nullable=False)
    WKL_DT_52 = Column("52WKLDT", String(11), nullable=False)
    group_id = Column(String(36), nullable=False, index=True)

class CircuitUpLowUpload(Base):
    __tablename__ = "circuit_up_low_upload"

    id = Column(Integer, primary_key=True, index=True)
    group_id = Column(String(36), index=True, nullable=False)
    upload_date = Column(Date, nullable=False)
    data_date = Column(Date, nullable=False)
    category = Column(String(100), nullable=False)
    file_name = Column(String(255), nullable=False)
    file_path = Column(String(500), nullable=False)