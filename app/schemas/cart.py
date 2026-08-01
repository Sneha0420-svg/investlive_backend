from pydantic import BaseModel
from datetime import datetime


class CartCreate(BaseModel):
    user_id: int
    username: str
    company: str
    isin: str
    doc_type: str
    year: str
    price: int
    document_id: str


class CartResponse(BaseModel):
    id: int
    user_id: int
    username: str
    company: str
    isin: str
    doc_type: str
    year: str
    price: int
    document_id: str
    created_at: datetime

    class Config:
        from_attributes = True
        
class BulkCartCreate(BaseModel):
    user_id: int
    username: str
    document_ids: list[str]