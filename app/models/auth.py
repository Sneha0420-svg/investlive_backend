from sqlalchemy import Column, Integer, String, Boolean, DateTime, Text
from app.database import Base
from datetime import datetime

class User(Base):
    __tablename__ = "users"

    userid = Column(Integer, primary_key=True, index=True)

    name = Column(String(100), nullable=False)

    provider = Column(String, nullable=True)
    provider_id = Column(String, index=True, nullable=True)

    email = Column(String, unique=True, index=True, nullable=True)

    google_access_token = Column(Text, nullable=True)
    google_refresh_token = Column(Text, nullable=True)
    google_token_expiry = Column(DateTime, nullable=True)  # ✅ new

    phone = Column(String(20), unique=True, nullable=True, index=True)
    profession = Column(String(50), nullable=True)

    password_hash = Column(String(256), nullable=False)

    is_active = Column(Boolean, default=True, nullable=False)

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    google_sync_enabled = Column(Boolean, default=False)