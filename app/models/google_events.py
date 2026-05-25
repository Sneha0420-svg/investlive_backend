# model/goog_events.py

from sqlalchemy import Boolean, Column, Integer, String,DateTime
from datetime import datetime
from app.database import Base

class GoogleEvent(Base):
    __tablename__ = "google_events"

    id = Column(Integer, primary_key=True)

    user_id = Column(Integer, index=True)
    ipo_name = Column(String)
    event_type = Column(String)
    event_date = Column(String)

    google_event_id = Column(String)
    synced_google = Column(Boolean, default=False)

    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
class GoogleSyncQueue(Base):
    __tablename__ = "google_sync_queue"

    id = Column(Integer, primary_key=True)

    user_id = Column(Integer, index=True)

    action = Column(String)  # create | update | delete

    ipo_name = Column(String)
    event_type = Column(String)
    event_date = Column(String)

    status = Column(String, default="pending")  # pending | done | failed

    google_event_id = Column(String, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow)