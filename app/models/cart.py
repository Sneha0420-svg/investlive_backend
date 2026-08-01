from sqlalchemy import Column, Integer, String, DateTime, ForeignKey
from datetime import datetime
from app.database import Base


class Cart(Base):
    __tablename__ = "cart"

    id = Column(Integer, primary_key=True, index=True)

    user_id = Column(Integer, nullable=False, index=True)
    username = Column(String(255), nullable=False)

    company = Column(String(255), nullable=False)
    isin = Column(String(20), nullable=False)
    doc_type = Column(String(100), nullable=False)
    year = Column(String(20), nullable=False)
    price = Column(Integer, nullable=False)

    document_id = Column(
        String(20),
        ForeignKey("reports.document_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    created_at = Column(DateTime, default=datetime.utcnow)