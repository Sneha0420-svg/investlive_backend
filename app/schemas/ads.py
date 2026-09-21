from pydantic import BaseModel, HttpUrl
from typing import Optional
from datetime import datetime


class AdBase(BaseModel):
    company_name: str
    company_website: Optional[HttpUrl]
    extra_info: Optional[str]

class AdCreate(AdBase):
    pass

class AdResponse(AdBase):
    id: int
    image_url: str
    uploaded_at: str
class VideoAdResponse(BaseModel):
    id: int
    video_url: str
    uploaded_at: datetime

    class Config:
        from_attributes = True
    class Config:
        orm_mode = True