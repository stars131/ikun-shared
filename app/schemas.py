from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class ResourceBase(BaseModel):
    title: str
    description: str = ""
    category: str
    tags: str = ""
    author: str = "匿名用户"
    external_url: str = ""
    file_path: str = ""
    preview_image: str = ""


class ResourceCreate(ResourceBase):
    pass


class ResourceOut(ResourceBase):
    id: int
    downloads: int
    created_at: datetime

    class Config:
        from_attributes = True


class Message(BaseModel):
    message: str
    detail: Optional[str] = None
