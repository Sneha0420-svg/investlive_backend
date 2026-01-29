from datetime import date
from typing import Optional
from pydantic import BaseModel

# -----------------------------
# Schemas for IPO Yearly Summary
# -----------------------------
class IPOHeatmapYearBase(BaseModel):
    year: int
    cos: Optional[int] = None
    ipo_value: Optional[float] = None
    market_value: Optional[float] = None
    ch_per: Optional[float] = None

class IPOHeatmapYearCreate(IPOHeatmapYearBase):
    pass

class IPOHeatmapYearRead(IPOHeatmapYearBase):
    id: int

    class Config:
        orm_mode = True

# -----------------------------
# Schemas for Yearly Uploads
# -----------------------------
class IPOHeatmapYearUploadBase(BaseModel):
    upload_date: date
    data_date: date
    data_type: str
    file_name: str
    file_path: str

class IPOHeatmapYearUploadCreate(IPOHeatmapYearUploadBase):
    pass

class IPOHeatmapYearUploadRead(IPOHeatmapYearUploadBase):
    id: int

    class Config:
        orm_mode = True

# -----------------------------
# Schemas for IPO Data
# -----------------------------
class IPOHeatmapDataBase(BaseModel):
    company: str
    iss_open: Optional[date] = None
    offer_price: Optional[float] = None
    cmp: Optional[float] = None
    ipo_value: Optional[float] = None
    cur_value: Optional[float] = None
    gain_per: Optional[float] = None

class IPOHeatmapDataCreate(IPOHeatmapDataBase):
    pass

class IPOHeatmapDataRead(IPOHeatmapDataBase):
    id: int

    class Config:
        orm_mode = True

# -----------------------------
# Schemas for IPO Data Uploads
# -----------------------------
class IPOHeatmapDataUploadBase(BaseModel):
    upload_date: date
    data_date: date
    data_type: str
    file_name: str
    file_path: str

class IPOHeatmapDataUploadCreate(IPOHeatmapDataUploadBase):
    pass

class IPOHeatmapDataUploadRead(IPOHeatmapDataUploadBase):
    id: int

    class Config:
        orm_mode = True
