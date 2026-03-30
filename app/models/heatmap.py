from sqlalchemy import Column, Integer, Numeric, String, SmallInteger, Date, BigInteger
from app.database import Base


# =========================
# COMPANY
# =========================
class Company(Base):
    __tablename__ = "company"

    pk_id = Column(BigInteger, primary_key=True, autoincrement=True)

    ID = Column(Integer, index=True)
    RANK = Column(Integer, index=True)

    COMPANY = Column(String(25))

    MCAP = Column(Numeric(20, 2))
    DAYCHCR = Column(Numeric(20, 2))
    CH = Column(Numeric(20, 1))

    FFLOAT = Column(Numeric(20, 2))
    FFRNK = Column(Integer)

    WKCHCR = Column(Numeric(20, 2))
    WKCH = Column(Numeric(20, 1))

    MTHCHCR = Column(Numeric(20, 2))
    MTHCH = Column(Numeric(20, 1))

    QTRCHCR = Column(Numeric(20, 2))
    QTRCH = Column(Numeric(20, 1))

    HYCHCR = Column(Numeric(20, 2))
    HYCH = Column(Numeric(20, 1))

    YRCHCR = Column(Numeric(20, 2))
    YRCH = Column(Numeric(20, 1))

    CMP = Column(Numeric(20, 2))
    PCL = Column(Numeric(20, 2))
    CH_RS = Column(Numeric(20, 2))
    CH_PER = Column(Numeric(20, 1))

    OPEN = Column(Numeric(20, 2))
    HIGH = Column(Numeric(20, 2))
    LOW = Column(Numeric(20, 2))
    CLOSE = Column(Numeric(20, 2))

    VOL = Column(Numeric(20, 3))
    VALUE = Column(Numeric(20, 3))

    TRADE = Column(BigInteger)  # ✅ FIXED

    ISIN = Column(String(45))
    SEC_ID = Column(String(45))
    ISCCODE = Column(String(45))

    INDUSTRY = Column(String(45))
    IND_RNK = Column(Integer)

    IH_MCODE = Column(Numeric(20, 6))
    IH_MNAME = Column(String(50))

    HOU_RNK = Column(Integer)

    COMPANY_NAME = Column(String(100))

    BSE = Column(String(10))
    NSE = Column(String(10))

    INDEX_STK = Column(SmallInteger)

    RONW = Column(Numeric(20, 2))
    ROCE = Column(Numeric(20, 2))

    EPS = Column(Numeric(20, 2))
    CEPS = Column(Numeric(20, 2))

    P_E = Column(Numeric(20, 2))
    P_CE = Column(Numeric(20, 2))

    DIV = Column(Numeric(20, 2))
    YLD = Column(Numeric(20, 2))

    DEBT_EQ = Column(Numeric(20, 2))


# =========================
# HOUSE
# =========================
class House(Base):
    __tablename__ = "house"

    pk_id = Column(BigInteger, primary_key=True, autoincrement=True)

    ID = Column(Integer, index=True)

    RNK = Column(Integer)

    IH_PR = Column(Numeric(10, 6))
    IH_AF = Column(Numeric(10, 6))

    HOUSE = Column(String(50))
    COS = Column(String(100))

    MCAP = Column(Numeric(20, 2))
    DAYCHCR = Column(Numeric(20, 2))
    CH = Column(Numeric(20, 1))

    FFLOAT = Column(Numeric(20, 2))
    FFRNK = Column(Integer)

    WKCHCR = Column(Numeric(20, 2))
    WKCH = Column(Numeric(20, 1))

    MTHCHCR = Column(Numeric(20, 2))
    MTHCH = Column(Numeric(20, 1))

    QTRCHCR = Column(Numeric(20, 2))
    QTRCH = Column(Numeric(20, 1))

    HYCHCR = Column(Numeric(20, 2))
    HYCH = Column(Numeric(20, 1))

    YRCHCR = Column(Numeric(20, 2))
    YRCH = Column(Numeric(20, 1))  # ✅ fixed duplicate


# =========================
# INDUSTRY
# =========================
class Industry(Base):
    __tablename__ = "industry"

    pk_id = Column(BigInteger, primary_key=True, autoincrement=True)

    ID = Column(Integer, index=True)

    RNK = Column(Integer)

    INDUSTRY = Column(String(45))
    COS = Column(Integer)

    MCAP = Column(Numeric(20, 2))
    DAYCHCR = Column(Numeric(20, 2))
    CH = Column(Numeric(20, 1))

    FFLOAT = Column(Numeric(20, 2))
    FFRNK = Column(Integer)

    WKCHCR = Column(Numeric(20, 2))
    WKCH = Column(Numeric(20, 1))

    MTHCHCR = Column(Numeric(20, 2))
    MTHCH = Column(Numeric(20, 1))

    QTRCHCR = Column(Numeric(20, 2))
    QTRCH = Column(Numeric(20, 1))

    HYCHCR = Column(Numeric(20, 2))
    HYCH = Column(Numeric(20, 1))

    YRCHCR = Column(Numeric(20, 2))
    YRCH = Column(Numeric(20, 1))

    SECID = Column(String(45))
    ISCCODE = Column(String(45))


# =========================
# SECTOR
# =========================
class Sector(Base):
    __tablename__ = "sector"

    pk_id = Column(BigInteger, primary_key=True, autoincrement=True)

    ID = Column(Integer, index=True)

    RNK = Column(Integer)

    SECTOR = Column(String(45))
    COS = Column(Integer)

    MCAP = Column(Numeric(20, 2))
    DAYCHCR = Column(Numeric(20, 2))
    CH = Column(Numeric(20, 1))

    FFLOAT = Column(Numeric(20, 2))
    FFRNK = Column(Integer)

    WKCHCR = Column(Numeric(20, 2))
    WKCH = Column(Numeric(20, 1))

    MTHCHCR = Column(Numeric(20, 2))
    MTHCH = Column(Numeric(20, 1))

    QTRCHCR = Column(Numeric(20, 2))
    QTRCH = Column(Numeric(20, 1))

    HYCHCR = Column(Numeric(20, 2))
    HYCH = Column(Numeric(20, 1))

    YRCHCR = Column(Numeric(20, 2))
    YRCH = Column(Numeric(20, 1))

    SECID = Column(String(45))


# =========================
# UPLOAD TABLES
# =========================
class CompanyUpload(Base):
    __tablename__ = "company_upload"

    id = Column(Integer, primary_key=True, index=True)
    group_id = Column(String(36), index=True)
    upload_date = Column(Date)
    data_date = Column(Date)
    data_type = Column(String(100))
    file_name = Column(String(255))
    file_path = Column(String(500))


class HouseUpload(Base):
    __tablename__ = "house_upload"

    id = Column(Integer, primary_key=True, index=True)
    group_id = Column(String(36), index=True)
    upload_date = Column(Date)
    data_date = Column(Date)
    data_type = Column(String(100))
    file_name = Column(String(255))
    file_path = Column(String(500))


class IndustryUpload(Base):
    __tablename__ = "industry_upload"

    id = Column(Integer, primary_key=True, index=True)
    group_id = Column(String(36), index=True)
    upload_date = Column(Date)
    data_date = Column(Date)
    data_type = Column(String(100))
    file_name = Column(String(255))
    file_path = Column(String(500))


class SectorUpload(Base):
    __tablename__ = "sector_upload"

    id = Column(Integer, primary_key=True, index=True)
    group_id = Column(String(36), index=True)
    upload_date = Column(Date)
    data_date = Column(Date)
    data_type = Column(String(100))
    file_name = Column(String(255))
    file_path = Column(String(500))