from sqlalchemy import Column, Integer, String, Text,DateTime
from app.database import Base
from datetime import datetime

class Announcement(Base):
    __tablename__ = "announcements"

    id = Column(Integer, primary_key=True, index=True)
    announcement_date = Column(DateTime, default=datetime.utcnow)
    company = Column(String(255), nullable=False)
    announcement= Column(Text, nullable=False)
    announcements_type = Column(String(100), default="General")
    image_path = Column(String(255), nullable=True)
    file_path = Column(String(255), nullable=True)
