from pydantic import BaseModel
from typing import Optional
from datetime import date

class VolumetradeBase(BaseModel):
    company:Optional[str]
    isin: Optional[str]
    mcap: Optional[str]
    cmp: Optional[str]
    volume: Optional[str]
    spurt: Optional[str]
    chper: Optional[str]
    five_dvma: Optional[str]
    twentyone_dvma: Optional[str]
    sixty_dvma: Optional[str]
    two_four_five_dvma: Optional[str]
    five_two_wkhv: Optional[str]
    five_two_wklv: Optional[str]
    upload_date: date
    data_date: date

class DataUploadCreate(VolumetradeBase):
    pass


class DataUploadResponse(VolumetradeBase):
    id: int
class UploadSummaryResponse(BaseModel):
    id: int
    upload_date: date
    data_date: date
    data_type: str
    file_name1: Optional[str]
    file_name2: Optional[str]
    file_name3: Optional[str]
    file_link1: Optional[str]
    file_link2: Optional[str]
    file_link3: Optional[str]
class UploadSummaryMultiFiles(BaseModel):
    id: int
    upload_date: date
    data_date: date

    file_name1: Optional[str] = None
    file_link1: Optional[str] = None

    file_name2: Optional[str] = None
    file_link2: Optional[str] = None

    file_name3: Optional[str] = None
    file_link3: Optional[str] = None
    class Config:
        from_attributes = True
