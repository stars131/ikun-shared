from typing import Optional

from sqlalchemy import desc, or_
from sqlalchemy.orm import Session

from .models import Resource
from .schemas import ResourceCreate


def create_resource(db: Session, payload: ResourceCreate) -> Resource:
    resource = Resource(**payload.model_dump())
    db.add(resource)
    db.commit()
    db.refresh(resource)
    return resource


def get_resource(db: Session, resource_id: int) -> Optional[Resource]:
    return db.query(Resource).filter(Resource.id == resource_id).first()


def list_resources(
    db: Session,
    query: str = "",
    category: str = "",
    sort: str = "latest",
    limit: int = 60,
):
    statement = db.query(Resource)
    if query:
        pattern = f"%{query.strip()}%"
        statement = statement.filter(
            or_(
                Resource.title.ilike(pattern),
                Resource.description.ilike(pattern),
                Resource.tags.ilike(pattern),
                Resource.author.ilike(pattern),
            )
        )
    if category and category != "all":
        statement = statement.filter(Resource.category == category)
    if sort == "popular":
        statement = statement.order_by(desc(Resource.downloads), desc(Resource.created_at))
    else:
        statement = statement.order_by(desc(Resource.created_at))
    return statement.limit(limit).all()


def increase_download(db: Session, resource: Resource) -> Resource:
    resource.downloads += 1
    db.add(resource)
    db.commit()
    db.refresh(resource)
    return resource
