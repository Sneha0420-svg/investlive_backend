from pydantic import BaseModel, HttpUrl
from typing import Optional

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

    class Config:
        orm_mode = True