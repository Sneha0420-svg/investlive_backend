from pydantic import BaseModel
from datetime import date

class MarketDateCreate(BaseModel):
    mkt_date: date