from sqlalchemy import Column, Integer, String, Text, DateTime, Numeric,Date
from app.database import Base
from datetime import datetime


class ReitInvitDebenture(Base):
    __tablename__ = "reit_invit_debenture"

    id = Column(Integer, primary_key=True, index=True)
    category = Column(String(100), nullable=True)
    company = Column(String(255), nullable=True)
    lead_manager = Column(String(255), nullable=True)
    issue_start = Column(Date, nullable=True)
    issue_end = Column(Date, nullable=True)
    issue_price = Column(Numeric(10, 2), nullable=True)
    logo_image = Column(String(255), nullable=True)
    content = Column(Text, nullable=True)
    pdf_path = Column(String(255), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)