from collections import Counter
from datetime import datetime, timedelta
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
) -> list[Resource]:
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


def _trend_score(resource: Resource, now: datetime, window_days: int) -> float:
    age_days = max(0.0, (now - resource.created_at).total_seconds() / 86400.0)
    freshness_bonus = max(0.0, window_days - age_days)
    return resource.downloads * 5 + resource.likes * 3 + resource.favorites * 4 + freshness_bonus


def list_trending(db: Session, days: int | None = 7, limit: int = 20) -> list[Resource]:
    statement = db.query(Resource)
    now = datetime.utcnow()
    if days:
        start_time = now - timedelta(days=days)
        statement = statement.filter(Resource.created_at >= start_time)
    resources = statement.all()
    window_days = days or 90
    resources.sort(
        key=lambda item: (_trend_score(item, now, window_days), item.downloads, item.created_at),
        reverse=True,
    )
    ranked = resources[:limit]
    for item in ranked:
        item.trending_score = round(_trend_score(item, now, window_days), 2)
    return ranked


def get_category_counts(db: Session) -> dict[str, int]:
    rows = db.query(Resource.category, Resource.id).all()
    counter: Counter[str] = Counter()
    for category, _ in rows:
        counter[category] += 1
    return dict(counter)


def list_hot_tags(db: Session, limit: int = 20) -> list[tuple[str, int]]:
    resources = db.query(Resource.tags, Resource.category).all()
    counter: Counter[str] = Counter()
    for tags, category in resources:
        if tags:
            for value in Resource(tags=tags, title="", category=category).tag_list:
                counter[value] += 1
        else:
            counter[Resource(category=category, title="").category_label] += 1
    return counter.most_common(limit)


def increase_download(db: Session, resource: Resource) -> Resource:
    resource.downloads += 1
    db.add(resource)
    db.commit()
    db.refresh(resource)
    return resource


def increase_like(db: Session, resource: Resource) -> Resource:
    resource.likes += 1
    db.add(resource)
    db.commit()
    db.refresh(resource)
    return resource


def increase_favorite(db: Session, resource: Resource) -> Resource:
    resource.favorites += 1
    db.add(resource)
    db.commit()
    db.refresh(resource)
    return resource
