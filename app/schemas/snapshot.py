from pydantic import BaseModel
from typing import Optional
from datetime import datetime


# -------------------------------------------------------
# Base Schema
# -------------------------------------------------------

class SnapshotBase(BaseModel):
    company: str
    exchange: str
    content: str


# -------------------------------------------------------
# Create Schema
# -------------------------------------------------------

class SnapshotCreate(SnapshotBase):
    pass


# -------------------------------------------------------
# Response Schema
# -------------------------------------------------------

class SnapshotResponse(SnapshotBase):
    id: int
    logo_image: Optional[str] = None
    pdf_path: Optional[str] = None
    created_at: datetime

    model_config = {
        "from_attributes": True  # Required for SQLAlchemy ORM
    }