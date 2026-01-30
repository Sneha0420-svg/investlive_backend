from sqlalchemy import Column, Integer, String, Text,DateTime
from datetime import datetime

from app.database import Base


class News(Base):
    __tablename__ = "news"

    id = Column(Integer, primary_key=True, index=True)
    news_date = Column(DateTime, default=datetime.utcnow)
    source = Column(String(100), nullable=False)
    heading = Column(String(150), nullable=False)
    title = Column(String(150), nullable=True)
    content = Column(Text, nullable=False)
    news_type = Column(String(50), nullable=False, default="General")
    image_path = Column(String(255), nullable=True)  # path to uploaded image
