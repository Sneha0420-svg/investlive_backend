from sqlalchemy import Column, Integer, String, Numeric, Date
from app.database import Base


class Bonus(Base):
    __tablename__ = "bonus"

    ID = Column(Integer, primary_key=True, index=True, autoincrement=True)

    ISIN = Column(String(12), nullable=False)
    BONUS = Column(Numeric(7, 2), nullable=False)
    PRE = Column(Numeric(7, 2), nullable=False)
    EX_DT = Column(Date, nullable=True)
    INDIC = Column(String(2), nullable=True)

class BonusUpload(Base):
    __tablename__="bonus_upload"
    
    id = Column(Integer, primary_key=True, index=True)
    group_id = Column(String(36), index=True, nullable=False)
    upload_date = Column(Date, nullable=False)
    data_date = Column(Date, nullable=False)
    data_type = Column(String(100), nullable=False) 
    file_name = Column(String(255), nullable=False)
    file_path = Column(String(500), nullable=False)  

class Split(Base):
    __tablename__ = "split"

    ID = Column(Integer, primary_key=True, index=True, autoincrement=True)

    ISIN = Column(String(12), nullable=False)
    OLD_FV = Column(Numeric(7, 2), nullable=False)
    NEW_FV = Column(Numeric(7, 2), nullable=False)
    EX_DT = Column(Date, nullable=True)
    INDIC = Column(String(2), nullable=True)
    
class SplitUpload(Base):
    __tablename__="split_upload"
    
    id = Column(Integer, primary_key=True, index=True)
    group_id = Column(String(36), index=True, nullable=False)
    upload_date = Column(Date, nullable=False)
    data_date = Column(Date, nullable=False)
    data_type = Column(String(100), nullable=False) 
    file_name = Column(String(255), nullable=False)
    file_path = Column(String(500), nullable=False)


class Div(Base):
    __tablename__ = "dividend"

    ID = Column(Integer, primary_key=True, index=True, autoincrement=True)

    ISIN = Column(String(12), nullable=False)
    DIV_RATE = Column(Numeric(7, 2), nullable=False)
    DIV_TYPE = Column(String(15), nullable=True)
    EX_DT = Column(Date, nullable=True)

class DivUpload(Base):
    __tablename__="div_upload"
    
    id = Column(Integer, primary_key=True, index=True)
    group_id = Column(String(36), index=True, nullable=False)
    upload_date = Column(Date, nullable=False)
    data_date = Column(Date, nullable=False)
    data_type = Column(String(100), nullable=False) 
    file_name = Column(String(255), nullable=False)
    file_path = Column(String(500), nullable=False)