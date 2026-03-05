from pydantic import BaseModel
from typing import Optional
from datetime import datetime


# -------------------------------------------------------
# Base Schema
# -------------------------------------------------------

class CurtainRaiserBase(BaseModel):
    company: str
    exchange: str
    content: str


# -------------------------------------------------------
# Create Schema
# -------------------------------------------------------

class CurtainRaiserCreate(CurtainRaiserBase):
    pass


# -------------------------------------------------------
# Response Schema
# -------------------------------------------------------

class CurtainRaiserResponse(CurtainRaiserBase):
    id: int
    logo_image: Optional[str] = None
    pdf_path: Optional[str] = None
    created_at: datetime

    model_config = {
        "from_attributes": True  # Required for SQLAlchemy ORM
    }