from typing import Optional, List
from pydantic import BaseModel
from datetime import date

class StockPulseDataSchema(BaseModel):
    scrip_code: Optional[str] = None
    scrip: Optional[str] = None
    co_code: Optional[str] = None
    isin: Optional[str] = None
    fv: Optional[float] = None
    cmp: Optional[float] = None

    dma_5: Optional[float] = None
    dma_21: Optional[float] = None
    dma_60: Optional[float] = None
    dma_245: Optional[float] = None

    wkh_52: Optional[float] = None
    wkhdt_52: Optional[date] = None
    wkl_52: Optional[float] = None
    wkldt_52: Optional[date] = None

    cur_vol: Optional[float] = None

    dvma_5: Optional[float] = None
    dvma_21: Optional[float] = None
    dvma_60: Optional[float] = None
    dvma_245: Optional[float] = None

    wkhv_52: Optional[float] = None
    wkhvdt_52: Optional[date] = None
    wklv_52: Optional[float] = None
    wklvdt_52: Optional[date] = None

    myrh: Optional[float] = None
    myrhdt: Optional[date] = None
    myrl: Optional[float] = None
    myrldt: Optional[date] = None
    myruh: Optional[float] = None
    myruhdt: Optional[date] = None
    myrul: Optional[float] = None
    myruldt: Optional[date] = None

    pulse_score: Optional[float] = None

    data_date: date
    type: str

    class Config:
        orm_mode = True

class StockPulseUploadSchema(BaseModel):
    id: int
    upload_date: date
    data_date: date
    data_type: str
    file_name: str
    file_link: str

class StockPulseLatestResponse(BaseModel):
    upload_date: date
    data_date: date
    type: str
    records: List[StockPulseDataSchema]
