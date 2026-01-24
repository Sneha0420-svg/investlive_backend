from datetime import date
from pydantic import BaseModel

class IpoEventBase(BaseModel):
    event_date: date
    company_name: str
    status: str


class IpoEventCreate(IpoEventBase):
    pass


class IpoEventUpdate(IpoEventBase):
    pass


class IpoEventResponse(IpoEventBase):
    id: int

    class Config:
        orm_mode = True
