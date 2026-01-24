from sqlalchemy import Column, Integer, String, Date
from app.database import Base

class IpoEvent(Base):
    __tablename__ = "ipo_events"

    id = Column(Integer, primary_key=True, index=True)
    event_date = Column(Date, nullable=False)
    company_name = Column(String(255), nullable=False)
    status = Column(String(50), nullable=False)
