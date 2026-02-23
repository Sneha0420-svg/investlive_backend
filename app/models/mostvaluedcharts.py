from sqlalchemy import Column, Integer, String, Date, DECIMAL
from app.database import Base

# ============================================================
# Most Valued Company Chart (Data Table)
# ============================================================
class MostValCompanyChart(Base):
    __tablename__ = "most_val_company_chart"

    ID = Column(Integer, primary_key=True, index=True, autoincrement=True)  # <-- added autoincrement
    COMPANY = Column(String(20), nullable=False)
    ISIN = Column(String(20), nullable=False)
    VAL = Column(Integer, nullable=False)
    TRN_DATE = Column(Date, nullable=False)
    group_id = Column(String(50), nullable=False, index=True)


# ============================================================
# Most Valued Company Upload Table
# ============================================================
class MostValCompanyChartUpload(Base):
    __tablename__ = "most_val_company_chart_upload"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)  # <-- added autoincrement
    group_id = Column(String(50), nullable=False, unique=True, index=True)
    upload_date = Column(Date, nullable=False)
    data_date = Column(Date, nullable=False)
    data_type = Column(String(50), default="MostValCompanyChart")
    file_name = Column(String(255), nullable=False)
    file_path = Column(String(500), nullable=False)


# ============================================================
# Most Valued House Chart (Data Table)
# ============================================================
class MostValHouseChart(Base):
    __tablename__ = "most_val_house_chart"

    ID = Column(Integer, primary_key=True, index=True, autoincrement=True)  # <-- added autoincrement
    H_ID = Column(DECIMAL(20, 6), nullable=False)
    HOUSE_NAME = Column(String(45), nullable=False)
    VALUE = Column(Integer, nullable=False)
    TRN_DATE = Column(Date, nullable=False)
    group_id = Column(String(50), nullable=False, index=True)


# ============================================================
# Most Valued House Upload Table
# ============================================================
class MostValHouseChartUpload(Base):
    __tablename__ = "most_val_house_chart_upload"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)  # <-- added autoincrement
    group_id = Column(String(50), nullable=False, unique=True, index=True)
    upload_date = Column(Date, nullable=False)
    data_date = Column(Date, nullable=False)
    data_type = Column(String(50), default="MostValHouseChart")
    file_name = Column(String(255), nullable=False)
    file_path = Column(String(500), nullable=False)