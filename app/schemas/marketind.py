from pydantic import BaseModel

class StockDataCreate(BaseModel):
    name: str
    year_ago: float
    current: float
    change_percent: float

class StockDataResponse(StockDataCreate):
    id: int

    class Config:
        orm_mode = True
