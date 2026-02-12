from sqlalchemy import Column, Integer, Date,String
from app.database import Base

class IndStockGraph(Base):
    __tablename__ = 'indstock_graph'

    ID = Column(Integer, primary_key=True, nullable=False)
    TRN_DATE = Column(Date, nullable=False)
    STKS_TRD = Column(Integer, nullable=False)
    ADV = Column(Integer, nullable=False)
    DECL = Column(Integer, nullable=False)
    UNCHG = Column(Integer, nullable=False)
    group_id = Column(String(36), nullable=False, index=True)  # Added group_id

class IndStockGraphUpload(Base):
    __tablename__ = "indstock_graph_upload"

    id = Column(Integer, primary_key=True, index=True)
    group_id = Column(String(36), index=True, nullable=False)
    upload_date = Column(Date, nullable=False)
    data_date = Column(Date, nullable=False)
    data_type = Column(String(100), nullable=False)
    file_name = Column(String(255), nullable=False)
    file_path = Column(String(500), nullable=False)
    