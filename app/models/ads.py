from sqlalchemy import Column, Integer, String, DateTime
from sqlalchemy.sql import func
from app.database import Base

class Ad(Base):
    __tablename__ = "ads"

    id = Column(Integer, primary_key=True, index=True)
    company_name = Column(String(255), nullable=False)
    company_website = Column(String(255), nullable=True)
    extra_info = Column(String(500), nullable=True)
    image_path = Column(String(500), nullable=False)  # S3 key
    uploaded_at = Column(DateTime(timezone=True), server_default=func.now())