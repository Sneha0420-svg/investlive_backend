from sqlalchemy import Column, Integer, String, Float, Date
from app.database import Base

class InstockTrendData(Base):
    __tablename__ = "indstocktrend"

    id = Column(Integer, primary_key=True, index=True)

    description = Column(String, nullable=False)
    count = Column(Float)
    day = Column(Float)
    week = Column(Float)
    month = Column(Float)
    quarter = Column(Float)
    halfyear = Column(Float)
    year = Column(Float)
    upload_date = Column(Date, nullable=False)  # new
    data_date = Column(Date, nullable=False)    # new
    type = Column(String, nullable=False)
class Indstocktrendupload(Base):
    __tablename__ = "indstocktrend_uploads"

    id = Column(Integer, primary_key=True, index=True)

    upload_date = Column(Date, nullable=False)
    data_date = Column(Date, nullable=False)
    data_type = Column(String(100), nullable=False)

    file_name = Column(String(255), nullable=False)
    file_path = Column(String(500), nullable=False)  # stored path or URL
