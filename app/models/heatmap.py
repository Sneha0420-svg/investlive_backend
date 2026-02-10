from sqlalchemy import Column, Integer, Numeric, String, SmallInteger,Date,BigInteger
from app.database import Base


class Company(Base):
    __tablename__ = "company"

    # ✅ NEW AUTO PRIMARY KEY
    pk_id = Column(BigInteger, primary_key=True, autoincrement=True)

    # ✅ CSV ID (can be duplicate)
    ID = Column(Integer, index=True)
    RANK= Column(Integer, index=True)
    COMPANY = Column(String(25))
    MCAP = Column(Numeric(20, 2), nullable=False)
    DAYCHCR = Column(Numeric(20, 2))
    CH = Column(Numeric(20, 1), nullable=False)
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
    CMP = Column(Numeric(20, 2), nullable=False)
    PCL = Column(Numeric(20, 2), nullable=False)
    CH_RS = Column(Numeric(20, 2), nullable=False)
    CH_PER = Column(Numeric(20, 1), nullable=False)
    OPEN = Column(Numeric(20, 2), nullable=False)
    HIGH = Column(Numeric(20, 2), nullable=False)
    LOW = Column(Numeric(20, 2), nullable=False)
    CLOSE = Column(Numeric(20, 2), nullable=False)
    VOL = Column(Numeric(20, 3), nullable=False)
    VALUE = Column(Numeric(20, 3), nullable=False)
    TRADE = Column(Integer, nullable=False)
    ISIN = Column(String(45), nullable=False)
    SEC_ID = Column(String(45), nullable=False)
    ISCCODE = Column(String(45), nullable=False)
    INDUSTRY = Column(String(45))
    IND_RNK = Column(Integer, nullable=False)
    IH_MCODE = Column(Numeric(20, 6), nullable=False)
    IH_MNAME = Column(String(50), nullable=True)
    HOU_RNK = Column(Integer, nullable=False)
    COMPANY_NAME = Column(String(100))
    BSE = Column(String(10))
    NSE = Column(String(10))
    INDEX_STK = Column(SmallInteger, nullable=False)
    RONW = Column(Numeric(20, 2), nullable=False)
    ROCE = Column(Numeric(20, 2), nullable=False)
    EPS = Column(Numeric(20, 2), nullable=False)
    CEPS = Column(Numeric(20, 2), nullable=False)
    P_E = Column(Numeric(20, 2), nullable=False)
    P_CE = Column(Numeric(20, 2), nullable=False)
    DIV = Column(Numeric(20, 2), nullable=False)
    YLD = Column(Numeric(20, 2), nullable=False)
    DEBT_EQ = Column(Numeric(20, 2), nullable=False)

class House(Base):
    __tablename__ = "house"

    # ✅ NEW AUTO PRIMARY KEY
    pk_id = Column(BigInteger, primary_key=True, autoincrement=True)

    # ✅ CSV ID (can be duplicate)
    ID = Column(Integer, index=True)

    RNK = Column(Integer, nullable=False)
    IH_PR = Column(Numeric(10, 6), nullable=False)
    IH_AF = Column(Numeric(10, 6), nullable=False)
    HOUSE = Column(String(50))
    COS = Column(String(100))

    MCAP = Column(Numeric(20, 2))
    DAYCHCR = Column(Numeric(20, 2))
    CH = Column(Numeric(20, 1))

    FFLOAT = Column(Numeric(20, 2), nullable=False)
    FFRNK = Column(Integer, nullable=False)

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
    YRCH = Column(Numeric(20, 1))

class Industry(Base):
    __tablename__ = "industry"

    # ✅ NEW AUTO PRIMARY KEY
    pk_id = Column(BigInteger, primary_key=True, autoincrement=True)

    # ✅ CSV ID (can be duplicate)
    ID = Column(Integer, index=True)
    RNK = Column(Integer, nullable=False)
    INDUSTRY = Column(String(45))
    COS = Column(Integer)
    MCAP = Column(Numeric(20, 2))
    DAYCHCR = Column(Numeric(20, 2))
    CH = Column(Numeric(20, 1))
    FFLOAT = Column(Numeric(20, 2), nullable=False)
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
    SECID = Column(String(45), nullable=False)
    ISCCODE = Column(String(45), nullable=False)
class CompanyUpload(Base):
    __tablename__ = "company_upload"

    id = Column(Integer, primary_key=True, index=True)
    group_id = Column(String(36), index=True, nullable=False)
    upload_date = Column(Date, nullable=False)
    data_date = Column(Date, nullable=False)
    data_type = Column(String(100), nullable=False) 
    file_name = Column(String(255), nullable=False)
    file_path = Column(String(500), nullable=False)  
class HouseUpload(Base):
    __tablename__ = "house_upload"

    id = Column(Integer, primary_key=True, index=True)
    group_id = Column(String(36), index=True, nullable=False)
    upload_date = Column(Date, nullable=False)
    data_date = Column(Date, nullable=False)
    data_type = Column(String(100), nullable=False) 
    file_name = Column(String(255), nullable=False)
    file_path = Column(String(500), nullable=False) 
class IndustryUpload(Base):
    __tablename__ = "industry_upload"

    id = Column(Integer, primary_key=True, index=True)
    group_id = Column(String(36), index=True, nullable=False)
    upload_date = Column(Date, nullable=False)
    data_date = Column(Date, nullable=False)
    data_type = Column(String(100), nullable=False)  # "tab1", "tab2", "tab3"
    file_name = Column(String(255), nullable=False)
    file_path = Column(String(500), nullable=False)  # stored path or URL
