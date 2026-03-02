# app/models/marketind.py

from sqlalchemy import Column, String, Date, Integer, Float, DateTime
from app.database import Base
from datetime import datetime

class MktGraph(Base):
    __tablename__ = "mkt_graph"

    SCRIP = Column(String(30), primary_key=True)
    PR_DATE = Column(Date, primary_key=True)
    CUR_CH = Column(Float, nullable=False)
    DMA5 = Column(Float, nullable=False)
    DMA21 = Column(Float, nullable=False)
    DMA60 = Column(Float, nullable=False)
    DMA245 = Column(Float, nullable=False)
    IDX_ID = Column(Integer, nullable=False)

class MktGraphUploads(Base):
    __tablename__ = "mkt_graph_uploads"

    id = Column(Integer, primary_key=True, autoincrement=True)
    filename = Column(String(100), nullable=False)
    upload_time = Column(DateTime, default=datetime.now)
    total_records = Column(Integer, default=0)
    errors = Column(Integer, default=0)