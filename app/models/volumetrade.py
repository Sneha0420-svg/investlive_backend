from sqlalchemy import BigInteger, Column, Integer, String, Float, Date
from app.database import Base

# Tab 1 Table
class VolumeTradevolume(Base):
    __tablename__ = "top_volume"

    id = Column(Integer, primary_key=True, index=True)
    data_date = Column(Date, nullable=False)

    company = Column(String, nullable=True)
    isin = Column(String, index=True, nullable=True)

    mcap = Column(BigInteger, nullable=True)
    cmp = Column(Float, nullable=True)

    volume = Column(BigInteger, nullable=True)
    spurt = Column(BigInteger, nullable=True)

    chper = Column(Integer, nullable=True)

    five_dvma = Column(BigInteger, nullable=True)
    twentyone_dvma = Column(BigInteger, nullable=True)
    sixty_dvma = Column(BigInteger, nullable=True)
    two_four_five_dvma = Column(BigInteger, nullable=True)

    five_two_wkhv = Column(BigInteger, nullable=True)
    five_two_wklv = Column(BigInteger, nullable=True)

    group_id = Column(String(36), index=True, nullable=False)

# Tab 2 Table
class VolumeTradevalue(Base):
    __tablename__ = "top_value"

    id = Column(Integer, primary_key=True, index=True)
    data_date = Column(Date, nullable=False)

    company = Column(String, nullable=True)
    isin = Column(String, index=True, nullable=True)

    mcap = Column(BigInteger, nullable=True)
    cmp = Column(Float, nullable=True)

    value = Column(BigInteger, nullable=True)
    spurt = Column(BigInteger, nullable=True)

    chper = Column(Integer, nullable=True)

    five_dvma = Column(BigInteger, nullable=True)
    twentyone_dvma = Column(BigInteger, nullable=True)
    sixty_dvma = Column(BigInteger, nullable=True)
    two_four_five_dvma = Column(BigInteger, nullable=True)

    five_two_wkhv = Column(BigInteger, nullable=True)
    five_two_wklv = Column(BigInteger, nullable=True)

    group_id = Column(String(36), index=True, nullable=False)

# Tab 3 Table
class VolumeTradetrade(Base):
    __tablename__ = "top_trade"

    id = Column(Integer, primary_key=True, index=True)
    data_date = Column(Date, nullable=False)

    company = Column(String, nullable=True)
    isin = Column(String, index=True, nullable=True)

    mcap = Column(BigInteger, nullable=True)
    cmp = Column(Float, nullable=True)

    trade = Column(BigInteger, nullable=True)
    spurt = Column(BigInteger, nullable=True)

    chper = Column(Integer, nullable=True)

    five_dvma = Column(BigInteger, nullable=True)
    twentyone_dvma = Column(BigInteger, nullable=True)
    sixty_dvma = Column(BigInteger, nullable=True)
    two_four_five_dvma = Column(BigInteger, nullable=True)

    five_two_wkhv = Column(BigInteger, nullable=True)
    five_two_wklv = Column(BigInteger, nullable=True)

    group_id = Column(String(36), index=True, nullable=False)
class VolumeTradeUpload(Base):
    __tablename__ = "volumetrade_upload"

    id = Column(Integer, primary_key=True, index=True)
    group_id = Column(String(36), index=True, nullable=False)
    data_date = Column(Date, nullable=False)
    data_type = Column(String(100), nullable=False)  # "tab1", "tab2", "tab3"
    file_name = Column(String(255), nullable=False)
    file_path = Column(String(500), nullable=False)  # stored path or URL
