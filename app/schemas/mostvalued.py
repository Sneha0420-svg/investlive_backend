from pydantic import BaseModel
from datetime import date
from typing import List

class MostvalueResponse(BaseModel):
    id: int
    name: str
    company:str
    day: float | None
    week: float | None
    month: float | None
    quarter: float | None
    halfyear: float | None
    year: float | None
    threeyear: float | None
   

    class Config:
        orm_mode = True

class MostvalueUploadWise(BaseModel):
    upload_date: date
    data_date: date
    data_type: str
    file_name: str | None
    rows: List[MostvalueResponse]