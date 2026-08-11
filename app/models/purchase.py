from sqlalchemy import (
    Column,
    Integer,
    Numeric,
    String,
    Float,
    DateTime,
    ForeignKey,
    Text
)

from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.database import Base


class PurchaseOrder(Base):
    __tablename__ = "purchase_orders"

    id = Column(Integer, primary_key=True, index=True)

    # Internal order id
    order_id = Column(String(100), unique=True, nullable=False, index=True)

    # Razorpay Order Id
    razorpay_order_id = Column(String(100), unique=True, nullable=True)

    # Razorpay Payment Id
    razorpay_payment_id = Column(String(100), nullable=True)

    # Razorpay Signature
    razorpay_signature = Column(Text, nullable=True)

    # User
    user_id = Column(
    Integer,
    ForeignKey("users.userid"),
    nullable=False,
    index=True
)
    

    # Total Amount
    amount = Column(Float, nullable=False)

    currency = Column(
        String(10),
        default="INR"
    )

    receipt = Column(
        String(100),
        unique=True,
        nullable=False
    )

    status = Column(
        String(20),
        default="PENDING"
    )

    created_at = Column(
        DateTime(timezone=True),
        server_default=func.now()
    )

    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now()
    )

    user = relationship(
        "User",
        back_populates="purchase_orders"
    )

    documents = relationship(
        "PurchasedDocument",
        back_populates="order",
        cascade="all, delete"
    )
    items = relationship(
    "PurchaseOrderItem",
    back_populates="order",
    cascade="all, delete-orphan"
)
    
class PurchasedDocument(Base):
    __tablename__ = "purchased_documents"

    id = Column(
        Integer,
        primary_key=True,
        index=True
    )

    purchase_order_id = Column(
        Integer,
        ForeignKey("purchase_orders.id"),
        nullable=False
    )
    user_id = Column(
    Integer,
    ForeignKey("users.userid"),
    nullable=False,
    index=True
)

   
    document_id = Column(
        String(100),
        nullable=False,
        index=True
    )

    company = Column(String(255))
    
    isin = Column(String(100),nullable=True)

    year = Column(Integer)

    document_type = Column(String(100))

    price = Column(Float)

    purchased_at = Column(
        DateTime(timezone=True),
        server_default=func.now()
    )

    order = relationship(
        "PurchaseOrder",
        back_populates="documents"
    )

    user = relationship(
        "User",
        back_populates="purchased_documents"
    )
    
class PurchaseOrderItem(Base):
    __tablename__ = "purchase_order_items"

    id = Column(
        Integer,
        primary_key=True,
        index=True
    )

    purchase_order_id = Column(
        Integer,
        ForeignKey("purchase_orders.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )

    document_id = Column(
        String(100),
        nullable=False,
        index=True
    )

    company = Column(
        String(255),
        nullable=False
    )
    isin = Column(String, nullable=True)

    year = Column(
        Integer,
        nullable=False
    )
    

    document_type = Column(
        String(100),
        nullable=False
    )

    price = Column(
        Numeric(10, 2),
        nullable=False
    )
    purchased_at = Column(
            DateTime(timezone=True),
            server_default=func.now()
        )

    order = relationship(
        "PurchaseOrder",
        back_populates="items"
    )
    