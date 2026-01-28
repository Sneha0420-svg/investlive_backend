from sqlalchemy import Column, Integer, String, Float, Date
from app.database import Base

# Tab 1 Table
class VolumeTradevolume(Base):
    __tablename__ = "volumetrade_tab1"

    id = Column(Integer, primary_key=True, index=True)
    upload_date = Column(Date, nullable=False)
    data_date = Column(Date, nullable=False)
    company = Column(String, nullable=True)
    isin = Column(String, index=True, nullable=True)
    mcap = Column(Float, nullable=True)
    cmp = Column(Float, nullable=True)
    volume = Column(Integer, nullable=True)
    spurt = Column(Integer, nullable=True)
    chper = Column(Integer, nullable=True)
    five_dvma = Column(Integer, nullable=True)
    twentyone_dvma = Column(Integer, nullable=True)
    sixty_dvma = Column(Integer, nullable=True)
    two_four_five_dvma = Column(Integer, nullable=True)
    five_two_wkhv = Column(Integer, nullable=True)
    five_two_wklv = Column(Integer, nullable=True)


# Tab 2 Table
class VolumeTradevalue(Base):
    __tablename__ = "volumetrade_tab2"

    id = Column(Integer, primary_key=True, index=True)
    upload_date = Column(Date, nullable=False)
    data_date = Column(Date, nullable=False)
    company = Column(String, nullable=True)
    isin = Column(String, index=True, nullable=True)
    mcap = Column(Float, nullable=True)
    cmp = Column(Float, nullable=True)
    volume = Column(Integer, nullable=True)
    spurt = Column(Integer, nullable=True)
    chper = Column(Integer, nullable=True)
    five_dvma = Column(Integer, nullable=True)
    twentyone_dvma = Column(Integer, nullable=True)
    sixty_dvma = Column(Integer, nullable=True)
    two_four_five_dvma = Column(Integer, nullable=True)
    five_two_wkhv = Column(Integer, nullable=True)
    five_two_wklv = Column(Integer, nullable=True)


# Tab 3 Table
class VolumeTradetrade(Base):
    __tablename__ = "volumetrade_tab3"

    id = Column(Integer, primary_key=True, index=True)
    upload_date = Column(Date, nullable=False)
    data_date = Column(Date, nullable=False)
    company = Column(String, nullable=True)
    isin = Column(String, index=True, nullable=True)
    mcap = Column(Float, nullable=True)
    cmp = Column(Float, nullable=True)
    volume = Column(Integer, nullable=True)
    spurt = Column(Integer, nullable=True)
    chper = Column(Integer, nullable=True)
    five_dvma = Column(Integer, nullable=True)
    twentyone_dvma = Column(Integer, nullable=True)
    sixty_dvma = Column(Integer, nullable=True)
    two_four_five_dvma = Column(Integer, nullable=True)
    five_two_wkhv = Column(Integer, nullable=True)
    five_two_wklv = Column(Integer, nullable=True)

class VolumeTradeUpload(Base):
    __tablename__ = "volumetrade_upload"

    id = Column(Integer, primary_key=True, index=True)
    group_id = Column(String(36), index=True, nullable=False)
    upload_date = Column(Date, nullable=False)
    data_date = Column(Date, nullable=False)
    data_type = Column(String(100), nullable=False)  # "tab1", "tab2", "tab3"
    file_name = Column(String(255), nullable=False)
    file_path = Column(String(500), nullable=False)  # stored path or URL
