from pydantic import BaseModel
from typing import Optional
from datetime import datetime

class AnnouncementBase(BaseModel):
    company: str
    announcement: str
    announcements_type: str = "General"

class AnnouncementCreate(AnnouncementBase):
    pass

class AnnouncementUpdate(AnnouncementBase):
    pass

class AnnouncementResponse(AnnouncementBase):
    id: int
    image_path: Optional[str] = None
    file_path: Optional[str] = None
    announcement_date: Optional[datetime] = None

    class Config:
        orm_mode = True
