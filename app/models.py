import re
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint

from .database import Base

CATEGORY_LABELS = {
    "video": "视频",
    "song": "歌曲",
    "image": "图片",
    "meme": "表情包",
    "other": "其他",
}


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
    likes = Column(Integer, default=0)
    favorites = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow, index=True)

    @property
    def category_label(self) -> str:
        return CATEGORY_LABELS.get(self.category, self.category)

    @property
    def file_name(self) -> str:
        if self.file_path:
            return Path(self.file_path).name or "资源文件"
        if self.external_url:
            parsed = urlparse(self.external_url)
            return Path(parsed.path).name or parsed.netloc or "外链资源"
        return "未上传文件"

    @property
    def tag_list(self) -> list[str]:
        raw_tags = re.split(r"[,\s，#]+", self.tags or "")
        tags: list[str] = []
        seen: set[str] = set()
        for tag in raw_tags:
            cleaned = tag.strip()
            if not cleaned:
                continue
            key = cleaned.lower()
            if key in seen:
                continue
            seen.add(key)
            tags.append(cleaned)
        if not tags:
            tags.append(self.category_label)
        return tags[:8]


class ResourceReaction(Base):
    __tablename__ = "resource_reactions"
    __table_args__ = (
        UniqueConstraint("resource_id", "client_token", "action", "day_key", name="uq_resource_reaction_daily"),
    )

    id = Column(Integer, primary_key=True, index=True)
    resource_id = Column(Integer, ForeignKey("resources.id", ondelete="CASCADE"), index=True, nullable=False)
    client_token = Column(String(64), index=True, nullable=False)
    action = Column(String(20), index=True, nullable=False)
    day_key = Column(String(10), index=True, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
