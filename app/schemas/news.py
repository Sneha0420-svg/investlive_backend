from pydantic import BaseModel
from typing import Optional
from datetime import datetime

class NewsBase(BaseModel):
    source: str
    heading: str
    title: Optional[str] = None
    content: str
    news_type: str
    news_date: Optional[datetime] = None  # NEW

class NewsCreate(NewsBase):
    pass

class NewsUpdate(NewsBase):
    pass

class NewsOut(NewsBase):
    id: int
    image_path: Optional[str] = None
    news_date: datetime  # Ensure response always includes date

    class Config:
        orm_mode = True
