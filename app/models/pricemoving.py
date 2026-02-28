# app/models/pricemoving.py
from sqlalchemy import Column, String, DECIMAL, Date, Integer
from app.database import Base
from sqlalchemy import UniqueConstraint

class PriceMoving(Base):
    __tablename__ = "pr_mvg"

    ID = Column(Integer, primary_key=True, index=True, autoincrement=True)

    SCCODE = Column(String(10))
    SCRIP = Column(String(30), nullable=False)
    COCODE = Column(String(6), nullable=False)
    ISIN = Column(String(12), nullable=False, index=True)
    CMP = Column(DECIMAL(10, 2), nullable=False)
    DMA_5 = Column("5DMA", DECIMAL(10, 2), nullable=False)
    DMA_21 = Column("21DMA", DECIMAL(10, 2), nullable=False)
    DMA_60 = Column("60DMA", DECIMAL(10, 2), nullable=False)
    DMA_245 = Column("245DMA", DECIMAL(10, 2), nullable=False)
    TRN_DATE = Column(Date, nullable=False, index=True)
    
    __table_args__ = (
        UniqueConstraint("ISIN", "TRN_DATE", name="unique_isin_date"),
    )