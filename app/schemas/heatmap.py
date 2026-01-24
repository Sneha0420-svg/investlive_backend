from pydantic import BaseModel
from typing import List, Optional
from datetime import date

class HeatMapBase(BaseModel):
    rank:int
    name: str
    cos: Optional[int]
    mcap: Optional[int]
    daych: Optional[int]
    daychper: Optional[float]
    ffltmcap: Optional[int]
    ffltrank: Optional[int]
    wkch: Optional[int]
    wkchper: Optional[float]
    mthch: Optional[int]
    mthchper: Optional[float]
    qtrch: Optional[int]
    qtrchper: Optional[float]
    hrch: Optional[int]
    hrchper: Optional[float]
    yrch: Optional[int]
    yrchper: Optional[float]

class HeatMapCreate(HeatMapBase):
    upload_id: int

class HeatMapOut(HeatMapBase):
    id: int
    upload_id: int

    class Config:
        orm_mode = True

class UploadBase(BaseModel):
    uploading_date: date
    data_date: date
    value: str
    filename: str
    file_path:str

class UploadCreate(UploadBase):
    pass

class UploadOut(UploadBase):
    id: int
    heatmapvalues: List[HeatMapOut] = []

    class Config:
        orm_mode = True
