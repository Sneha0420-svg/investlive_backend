from sqlalchemy import Column, Integer, String, Float, Date
from app.database import Base


class CorporateActionData(Base):
    __tablename__ = "corporate_actions"

    ID = Column(Integer, primary_key=True, index=True)

    SCRIP_CODE_SYMBOL = Column(String, nullable=False)
    SECURITY_NAME = Column(String, nullable=True)
    COMPANY = Column(String, nullable=False)
    SERIES = Column(String)

    EX_DATE = Column(Date)
    PURPOSE = Column(String)
    PURPOSE_VALUE = Column(String)
    RECORD_DATE = Column(Date)

    FACE_VALUE = Column(String)

    BC_START_DATE = Column(Date)
    BC_END_DATE = Column(Date)

    ND_START_DATE = Column(Date)
    ND_END_DATE = Column(Date)
    
    ACTUAL_PAYMENT_DATE = Column(Date)
    
    
class CorporateActionUpload(Base):
    __tablename__ = "corporate_action_uploads"


    id = Column(Integer, primary_key=True, index=True)

    mkt_date = Column(Date, nullable=False)

    file_name = Column(String(255), nullable=False)
    file_path = Column(String(500), nullable=False)  # stored path or URL
    
class ResultData(Base):
    __tablename__ = "corporate_action_results"

    id = Column(Integer, primary_key=True, index=True)
    scrip_code_symbol = Column(String, nullable=False)
    company = Column(String, nullable=False)
    Result_date = Column(Date)
   
class ResultUpload(Base):
    __tablename__ = "result_uploads"

    id = Column(Integer, primary_key=True, index=True)

    mkt_date = Column(Date, nullable=False)

    file_name = Column(String(255), nullable=False)
    file_path = Column(String(500), nullable=False)
    
    
    # ==============================
# MANUAL ENTRY MODEL
# ==============================

class ManualEntryUpload(Base):
    __tablename__ = "manual_entry_uploads"

    id = Column(Integer, primary_key=True, index=True)

    company_name = Column(String(255))

    purpose = Column(String(255))

    entry_date = Column(Date)