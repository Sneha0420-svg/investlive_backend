from sqlalchemy import Column, Integer, String, Float, Date
from app.database import Base

class Mostvalued(Base):
    __tablename__ = "mostvalueddata"

    id = Column(Integer, primary_key=True, index=True)

    name= Column(String, nullable=False)
    company=Column(String, nullable=False)
    day = Column(Float)
    week = Column(Float)
    month = Column(Float)
    quarter = Column(Float)
    halfyear = Column(Float)
    year = Column(Float)
    threeyear = Column(Float)
    upload_date = Column(Date, nullable=False)  
    data_date = Column(Date, nullable=False) 
    type = Column(String, nullable=False)

class MostValuedupload(Base):
    __tablename__ = "mostvaluedfiles"

    id = Column(Integer, primary_key=True, index=True)
    name= Column(String, nullable=False)
    upload_date = Column(Date, nullable=False)
    data_date = Column(Date, nullable=False)
    data_type = Column(String(100), nullable=False)

    file_name = Column(String(255), nullable=False)
    file_path = Column(String(500), nullable=False)  # stored path or URL
