from sqlalchemy import Column, Integer, String, DateTime, Numeric
from datetime import datetime
import uuid

from app.database import Base


class CompanyFile(Base):
    __tablename__ = "reports"

    id = Column(Integer, primary_key=True, index=True)

    document_id = Column(
        String(20),
        unique=True,
        nullable=False,
        index=True,
        default=lambda: "DOC" + uuid.uuid4().hex[:10].upper(),
    )

    isin = Column(String(12), nullable=False)
    company = Column(String(255), nullable=False)
    mcap=Column(String(30),nullable=False)
    year = Column(Integer, nullable=False)
    document_type = Column(String(100), nullable=False)
    treasure=Column(String(20))
    filename = Column(String(255), nullable=False)
    filepath = Column(String(500), nullable=False)
    total_pages = Column(Integer, default=0)
    file_size = Column(Integer)
    price = Column(Numeric(10, 2), default=199)
    uploaded_at = Column(DateTime, default=datetime.utcnow)