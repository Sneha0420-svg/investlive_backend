from pydantic import BaseModel
from typing import List
from datetime import date
from decimal import Decimal

class StockSchema(BaseModel):
    id: int
    name: str
    yr_ago: Decimal
    curnt: Decimal
    ch: Decimal
    H_ID: int
    S_ID: int
    IDX_ID: int
    flag: str
    mkt_date: date

class LatestStocksResponse(BaseModel):
    latest_mkt_date: date
    total_records: int
    stocks: List[StockSchema]