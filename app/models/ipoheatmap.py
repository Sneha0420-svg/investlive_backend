from sqlalchemy import Column, Integer, String, Float, Date, DateTime
from datetime import datetime
from app.database import Base

# ------------------------------
# Yearly IPO Summary
# ------------------------------
class IPOHeatmapYear(Base):
    __tablename__ = "ipo_heatmap_yearwise"

    id = Column(Integer, primary_key=True, index=True)
    year = Column(Integer,  unique=True, index=True)
    cos = Column(Integer)
    ipo_value = Column(Float)
    market_value = Column(Float)
    ch_per = Column(Float)


# ------------------------------
# Yearly IPO Uploads
# ------------------------------
class IPOHeatmapYearUpload(Base):
    __tablename__ = "ipo_heatmap_yearwise_uploads"

    id = Column(Integer, primary_key=True, index=True)
    upload_date = Column(Date, nullable=False, default=datetime.utcnow)
    data_date = Column(Date, nullable=False)
    data_type = Column(String(100), nullable=False)
    file_name = Column(String(255), nullable=False)
    file_path = Column(String(500), nullable=False)


# ------------------------------
# Individual IPO Data
# ------------------------------
class IPOHeatmapData(Base):
    __tablename__ = "ipo_heatmap_data"

    id = Column(Integer, primary_key=True, index=True)
    company = Column(String(255), index=True)
    iss_open = Column(Date)
    offer_price = Column(Float)
    cmp = Column(Float)
    ipo_value = Column(Float)
    cur_value = Column(Float)
    gain_per = Column(Float)


# ------------------------------
# IPO Data Uploads
# ------------------------------
class IPOHeatmapDataUpload(Base):
    __tablename__ = "ipo_heatmap_data_upload"

    id = Column(Integer, primary_key=True, index=True)
    upload_date = Column(Date, nullable=False, default=datetime.utcnow)
    data_date = Column(Date, nullable=False)
    data_type = Column(String(100), nullable=False)
    file_name = Column(String(255), nullable=False)
    file_path = Column(String(500), nullable=False)
