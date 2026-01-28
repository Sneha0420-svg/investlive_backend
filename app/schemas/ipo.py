from pydantic import BaseModel
from typing import Optional
from datetime import date

class DataUploadBase(BaseModel):
    isin: Optional[str]
    co_name: Optional[str]
    ibr_name: Optional[str]
    iss_open: Optional[date]
    iss_close: Optional[date]
    allotment_date: Optional[date]
    refund_dt: Optional[date]
    demat_dt: Optional[date]
    trading_dt: Optional[date]
    high: Optional[float]
    low: Optional[float]
    off_price: Optional[float]
    face_value: Optional[float]
    iss_amt: Optional[float]
    iss_qty: Optional[float]
    listed_pr: Optional[float]
    listed_gain: Optional[float]
    listed_dt: Optional[date]
    mkt_lot: Optional[float]
    subs_times: Optional[float]
    exch: Optional[str]
    iss_type: Optional[str]
    offer_type: Optional[str]
    offer_objective: Optional[str]
    state: Optional[str]
    signed_by: Optional[str]
    industry: Optional[str]
    lm1: Optional[str]
    lm2: Optional[str]
    lm3: Optional[str]
    lm4: Optional[str]
    lm5: Optional[str]
    lm6: Optional[str]
    lm7: Optional[str]
    lm8: Optional[str]
    lm9: Optional[str]
    lm10: Optional[str]
    lm11: Optional[str]
    lm12: Optional[str]
    lm13: Optional[str]
    lm14: Optional[str]
    lm15: Optional[str]
    mktmkr1: Optional[str]
    mktmkr2: Optional[str]
    mktmkr3: Optional[str]
    mktmkr4: Optional[str]
    mktmkr5: Optional[str]
    upload_date: date
    data_date: date

class DataUploadCreate(DataUploadBase):
    pass

class DataUploadUpdate(BaseModel):
    co_name: Optional[str]
    ibr_name: Optional[str]
    iss_open: Optional[date]
    # ... add other fields if needed

class DataUploadResponse(DataUploadBase):
    id: int
class UploadSummaryResponse(BaseModel):
    id: int
    upload_date: date
    data_date: date
    data_type: str
    file_name: str
    file_link: str
    class Config:
        from_attributes = True
