from pydantic import BaseModel
from datetime import date
from typing import List

class InstockTrendResponse(BaseModel):
    id: int
    description: str
    count: float | None
    day: float | None
    week: float | None
    month: float | None
    quarter: float | None
    halfyear: float | None
    year: float | None
   

    class Config:
        orm_mode = True

class InstockTrendUploadWise(BaseModel):
    upload_date: date
    data_date: date
    data_type: str
    file_name: str | None
    rows: List[InstockTrendResponse]