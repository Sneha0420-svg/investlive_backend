from pydantic import BaseModel
from typing import List
from decimal import Decimal
from datetime import datetime


# -----------------------------
# Request to Create Order
# -----------------------------

class PurchaseCreateRequest(BaseModel):
    document_ids: list[str]
    total: Decimal
    discount: Decimal = Decimal("0.00")
    gst: Decimal = Decimal("0.00")


# -----------------------------
# Verify Payment Request
# -----------------------------
class PurchasedDocumentRequest(BaseModel):
    document_id: str
    company: str
    year: int
    price: float
    
    
class PaymentVerifyRequest(BaseModel):
    razorpay_order_id: str
    razorpay_payment_id: str
    razorpay_signature: str
    documents: List[PurchasedDocumentRequest]


# -----------------------------
# Purchased Document Response
# -----------------------------

class PurchasedDocumentResponse(BaseModel):
    document_id: str
    company: str
    year: int
    document_type: str
    price: Decimal
    purchased_at: datetime

    class Config:
        from_attributes = True


# -----------------------------
# Purchase History Response
# -----------------------------

class PurchaseHistoryResponse(BaseModel):
    order_id: str
    amount: Decimal
    status: str
    created_at: datetime
    documents: List[PurchasedDocumentResponse]

    class Config:
        from_attributes = True