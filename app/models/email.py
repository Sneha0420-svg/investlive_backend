from sqlalchemy import Column, Integer, String, Boolean, DateTime
from app.database import Base
from datetime import datetime


class OneTimeLink(Base):
    __tablename__ = "one_time_links"

    id = Column(Integer, primary_key=True)
    token = Column(String, unique=True)
    url = Column(String)
    used = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)