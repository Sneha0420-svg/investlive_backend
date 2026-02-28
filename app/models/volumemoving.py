# app/models/volumemoving.py

from sqlalchemy import Column, String, Integer, Date, UniqueConstraint
from app.database import Base


class VolumeMoving(Base):
    __tablename__ = "vol_mvg"

    ID = Column(Integer, primary_key=True, index=True, autoincrement=True)

    SCCODE = Column(String(12), nullable=True)
    SCRIP = Column(String(30), nullable=True)
    COCODE = Column(String(6), nullable=True)
    ISIN = Column(String(12), nullable=True, index=True)
    CURVOL = Column(Integer, nullable=True)
    TRN_DATE = Column(Date, nullable=True, index=True)

    __table_args__ = (
        UniqueConstraint("ISIN", "TRN_DATE", name="CONS_VOL_ISIN_TRN"),
    )