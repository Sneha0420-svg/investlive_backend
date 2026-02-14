from sqlalchemy import Column, Integer, String, Date, DECIMAL
from app.database import Base


# --------------------------------------------------
# Lead Manager Ranking Table
# --------------------------------------------------
class LMRank(Base):
    __tablename__ = "lm_rank"

    id = Column("ID", Integer, primary_key=True, index=True,autoincrement=True)
    lm_code = Column("LM_CODE", String(6), nullable=False)
    lm_name = Column("LM_NAME", String(50), nullable=False)
    cos = Column("COS", Integer, nullable=False)

    ipo_val = Column("IPO_VAL", DECIMAL(20, 0), nullable=False)
    applications = Column("APPLICATIONS", DECIMAL(20, 0), nullable=False)
    subs_amount = Column("SUBS_AMOUNT", DECIMAL(20, 0), nullable=False)

    list_value = Column("LIST_VALUE", DECIMAL(20, 0), nullable=False)
    list_gain_per = Column("LIST_GAIN_PER", DECIMAL(20, 1), nullable=False)

    qtrly_value = Column("QTRLY_VALUE", DECIMAL(20, 0), nullable=False)
    qtr_gain_per = Column("QTR_GAIN_PER", DECIMAL(20, 1), nullable=False)

    hlf_yr_value = Column("HLF_YR_VALUE", DECIMAL(20, 0), nullable=False)
    hlf_gain_per = Column("HLF_GAIN_PER", DECIMAL(20, 1), nullable=False)

    yrly_value = Column("YRLY_VALUE", DECIMAL(20, 0), nullable=False)
    yr_gain_per = Column("YR_GAIN_PER", DECIMAL(20, 1), nullable=False)

    one_hlf_yr_value = Column("ONE_HLF_YR_VALUE", DECIMAL(20, 0), nullable=False)
    one_hlf_gain_per = Column("ONE_HLF_GAIN_PER", DECIMAL(20, 1), nullable=False)
    
    curr_value = Column("CURR_VALUE", DECIMAL(20, 0), nullable=False)
    cur_gain_per = Column("CUR_GAIN_PER", DECIMAL(20, 1), nullable=False)
    
    consol_rnk = Column("CONSOL_RNK", DECIMAL(20, 0), nullable=False)
    group_id = Column(String(36), nullable=False, index=True) 

# --------------------------------------------------
# Lead Manager Subscription Table
# --------------------------------------------------
class LMSub(Base):
    __tablename__ = "lm_sub"

    id = Column("ID", Integer, primary_key=True, index=True,autoincrement=True)
    lm_code = Column("LM_CODE", String(6), nullable=False)
    isin = Column("ISIN", String(12), nullable=False)
    company = Column("COMPANY", String(20), nullable=False)
    iss_open = Column("ISS_OPEN", Date, nullable=False)
    ipo_pr = Column("IPO_PR", DECIMAL(7, 2), nullable=False)
    ipo_val = Column("IPO_VAL", DECIMAL(20, 2), nullable=False)
    listed_pr = Column("LISTED_PR", DECIMAL(7, 2), nullable=False)
    cmp = Column("CMP", DECIMAL(7, 2), nullable=False)
    cur_val = Column("CUR_VAL", DECIMAL(20, 2), nullable=False)
    gain_val = Column("GAIN_VAL", DECIMAL(20, 2), nullable=False)
    gain_perc = Column("GAIN_PERC", DECIMAL(10, 1), nullable=False)
    group_id = Column(String(36), nullable=False, index=True) 

from sqlalchemy import Column, Integer, String, Date
from app.database import Base


# --------------------------------------------------
# Lead Manager Rank Upload Table
# --------------------------------------------------
class LMRankUpload(Base):
    __tablename__ = "lm_rank_upload"

    id = Column(Integer, primary_key=True, index=True)
    group_id = Column(String(36), index=True, nullable=False)
    upload_date = Column(Date, nullable=False)
    data_date = Column(Date, nullable=False)
    category = Column(String(100), nullable=False)
    file_name = Column(String(255), nullable=False)
    file_path = Column(String(500), nullable=False)


# --------------------------------------------------
# Lead Manager Subscription Upload Table
# --------------------------------------------------
class LMSubUpload(Base):
    __tablename__ = "lm_sub_upload"

    id = Column(Integer, primary_key=True, index=True)
    group_id = Column(String(36), index=True, nullable=False)
    upload_date = Column(Date, nullable=False)
    data_date = Column(Date, nullable=False)
    category = Column(String(100), nullable=False)
    file_name = Column(String(255), nullable=False)
    file_path = Column(String(500), nullable=False)
