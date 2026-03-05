from sqlalchemy import Column, Integer, String, Text, DateTime
from app.database import Base
from datetime import datetime


class PrimaryMusings(Base):
    __tablename__ = "primary_musings"

    id = Column(Integer, primary_key=True, index=True)
    company = Column(String(255), nullable=False)
    exchange=Column(String(25),nullable=False)
    logo_image = Column(String(255), nullable=True)   # stores logo file path
    content = Column(Text, nullable=False)
    pdf_path = Column(String(255), nullable=True)     # stores uploaded PDF path
    created_at = Column(DateTime, default=datetime.utcnow)