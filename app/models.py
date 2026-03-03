from datetime import datetime

from sqlalchemy import Column, DateTime, Integer, String, Text

from .database import Base


class Resource(Base):
    __tablename__ = "resources"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(200), nullable=False, index=True)
    description = Column(Text, default="")
    category = Column(String(50), nullable=False, index=True)
    tags = Column(String(255), default="")
    author = Column(String(100), default="匿名用户")
    external_url = Column(String(500), default="")
    file_path = Column(String(500), default="")
    preview_image = Column(String(500), default="")
    downloads = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
