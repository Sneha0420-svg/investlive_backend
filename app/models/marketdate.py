from sqlalchemy import Column, Date, Integer
from app.database import Base

class MarketDate(Base):
    __tablename__ = "mkt_date"

    id = Column(Integer, primary_key=True, index=True)
    mkt_date = Column(Date, nullable=False)