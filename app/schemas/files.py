from pydantic import BaseModel
from decimal import Decimal
from datetime import datetime

class ReportCreate(BaseModel):
    document_id: str
    isin: str
    company: str
    mcap:str
    year: int
    document_type: str
    treasure:str
    filename: str
    filepath: str
    total_pages: int = 0
    file_size: int | None = None
    price: Decimal = Decimal("199.00")


class ReportUpdate(BaseModel):
    isin: str | None = None
    company: str | None = None
    mcap:str
    year: int | None = None
    document_type: str | None = None
    treasure:str|None=None
    filename: str | None = None
    filepath: str | None = None
    total_pages: int | None = None
    file_size: int | None = None
    price: Decimal | None = None


class ReportResponse(BaseModel):
    id: int
    isin: str
    company: str
    mcap:str
    year: int
    document_type: str
    treasure:str
    document_id:str
    filename: str
    filepath: str
    total_pages: int
    file_size: int | None
    price: Decimal
    uploaded_at: datetime

    class Config:
        from_attributes = True