from pydantic import BaseModel
from decimal import Decimal
from typing import Optional, List


# ---------- 52 Week High / Low ----------
class FiftyTwoWeekHighLowBase(BaseModel):
    COMPANY: Optional[str]
    ISIN: str
    CMP: Decimal
    WKH_52: Decimal
    WKL_52: Decimal
    CH_RS: Decimal
    CH_PER: Decimal


class FiftyTwoWeekHighLowResponse(FiftyTwoWeekHighLowBase):
    class Config:
        orm_mode = True


# ---------- Multi Year High / Low ----------
class MultiYearHighLowBase(BaseModel):
    COMPANY: Optional[str]
    ISIN: str
    
    MCAP: Decimal
    CMP: Decimal
    MYRH: Decimal
    MYRH_DT: str
    MYRL: Decimal
    MYRL_DT: str
    SINCE: str
    TYPE: int
    ID: int


class MultiYearHighLowResponse(MultiYearHighLowBase):
    class Config:
        orm_mode = True
