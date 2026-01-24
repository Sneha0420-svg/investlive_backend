from sqlalchemy import Column, Integer, Float, String, ForeignKey, Date
from sqlalchemy.orm import relationship
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()

class Upload(Base):
    __tablename__ = "uploads"

    id = Column(Integer, primary_key=True, index=True)
    uploading_date = Column(Date, nullable=False)
    data_date = Column(Date, nullable=False)
    value = Column(String, nullable=False)  # e.g. Company, House, IndSegment
    filename = Column(String, nullable=False)  # Store filename or path if needed
    file_path = Column(String(500), nullable=False)

    # **Fix relationship to point to the ORM class**
    heatmapvalues = relationship("HeatMap", back_populates="upload", cascade="all, delete-orphan")


class HeatMap(Base):
    __tablename__ = "secmart_heatmap"

    id = Column(Integer, primary_key=True, index=True)
    upload_id = Column(Integer, ForeignKey("uploads.id"), nullable=False)
    rank = Column("rank", Integer, quote=True)

    name = Column(String, nullable=False)  # Company / Ministry name

    cos= Column(Integer)
    mcap = Column(Integer)
    daych = Column(Integer)
    daychper = Column(Float)
    ffltmcap = Column(Integer)
    ffltrank = Column(Integer)
    wkch = Column(Integer)
    wkchper = Column(Float)
    mthch = Column(Integer)
    mthchper = Column(Float)
    qtrch = Column(Integer)
    qtrchper = Column(Float)
    hrch = Column(Integer)
    hrchper = Column(Float)
    yrch = Column(Integer)
    yrchper = Column(Float)

    # **Link back to Upload**
    upload = relationship("Upload", back_populates="heatmapvalues")
