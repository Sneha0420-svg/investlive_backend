# models/auth.py

from sqlalchemy import Column, Integer, String, Boolean, DateTime
from app.database import Base
from datetime import datetime


class User(Base):
    __tablename__ = "users"

    userid = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False)
    email = Column(String(150), unique=True, nullable=False, index=True)
    phone = Column(String(20), unique=True, nullable=True, index=True)
    profession = Column(String(50), nullable=True)
    password_hash = Column(String(256), nullable=False)

    is_active = Column(Boolean, default=True, nullable=False)

    # Online Status Fields
    is_online = Column(Boolean, default=False, nullable=False)
    last_login = Column(DateTime, nullable=True)
    last_logout = Column(DateTime, nullable=True)
    last_seen = Column(DateTime, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False
    )

    def __repr__(self):
        return f"<User(userid={self.userid}, email={self.email})>"
    