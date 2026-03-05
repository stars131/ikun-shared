from collections import Counter
from datetime import datetime, timedelta
import re
import secrets
from typing import Optional

from sqlalchemy import desc, func, or_
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from .models import OAuthAccount, Resource, ResourceReaction, User
from .schemas import ResourceCreate


# ── Resource CRUD ──────────────────────────────────────────────────


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


def list_resources_paginated(
    db: Session,
    query: str = "",
    category: str = "",
    sort: str = "latest",
    page: int = 1,
    per_page: int = 20,
) -> tuple[list[Resource], int]:
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
    total = statement.count()
    offset = (page - 1) * per_page
    items = statement.offset(offset).limit(per_page).all()
    return items, total


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


def register_reaction(
    db: Session,
    resource: Resource,
    client_token: str,
    action: str,
) -> tuple[bool, Resource]:
    day_key = datetime.utcnow().strftime("%Y-%m-%d")
    exists = (
        db.query(ResourceReaction.id)
        .filter(
            ResourceReaction.resource_id == resource.id,
            ResourceReaction.client_token == client_token,
            ResourceReaction.action == action,
            ResourceReaction.day_key == day_key,
        )
        .first()
    )
    if exists:
        return False, resource

    reaction = ResourceReaction(
        resource_id=resource.id,
        client_token=client_token,
        action=action,
        day_key=day_key,
    )
    db.add(reaction)
    if action == "like":
        resource.likes += 1
    elif action == "favorite":
        resource.favorites += 1
    else:
        raise ValueError(f"Unsupported reaction action: {action}")
    db.add(resource)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        db.refresh(resource)
        return False, resource
    db.refresh(resource)
    return True, resource


# ── User CRUD ──────────────────────────────────────────────────────


class UsernameExistsError(Exception):
    pass


class OAuthAccountLinkError(Exception):
    pass


def create_user(db: Session, username: str, display_name: str, password_hash: str) -> User:
    user = User(username=username, display_name=display_name, password_hash=password_hash)
    db.add(user)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise UsernameExistsError from exc
    db.refresh(user)
    return user


def get_user_by_username(db: Session, username: str) -> Optional[User]:
    return db.query(User).filter(User.username == username).first()


def get_user_by_id(db: Session, user_id: int) -> Optional[User]:
    return db.query(User).filter(User.id == user_id).first()


def get_oauth_account(db: Session, provider: str, provider_user_id: str) -> Optional[OAuthAccount]:
    return (
        db.query(OAuthAccount)
        .filter(
            OAuthAccount.provider == provider,
            OAuthAccount.provider_user_id == provider_user_id,
        )
        .first()
    )


def get_user_by_oauth(db: Session, provider: str, provider_user_id: str) -> Optional[User]:
    account = get_oauth_account(db, provider, provider_user_id)
    if not account:
        return None
    return get_user_by_id(db, account.user_id)


def _normalize_oauth_username(raw: str) -> str:
    normalized = re.sub(r"[^a-zA-Z0-9_]+", "_", (raw or "").strip().lower()).strip("_")
    if not normalized:
        normalized = f"user_{secrets.token_hex(3)}"
    return normalized[:50]


def _pick_unique_username(db: Session, base_username: str) -> str:
    candidate = _normalize_oauth_username(base_username)
    if not get_user_by_username(db, candidate):
        return candidate

    for _ in range(8):
        suffix = secrets.token_hex(2)
        head = candidate[: max(1, 50 - len(suffix) - 1)]
        picked = f"{head}_{suffix}"
        if not get_user_by_username(db, picked):
            return picked
    return f"user_{secrets.token_hex(6)}"


def get_or_create_user_by_oauth(
    db: Session,
    *,
    provider: str,
    provider_user_id: str,
    provider_username: str,
    provider_display_name: str,
    password_hash: str,
) -> User:
    provider_key = (provider or "").strip().lower()[:32]
    provider_uid = (provider_user_id or "").strip()[:128]
    if not provider_key or not provider_uid:
        raise OAuthAccountLinkError("invalid oauth provider data")

    existing_user = get_user_by_oauth(db, provider_key, provider_uid)
    if existing_user:
        return existing_user

    local_username = _pick_unique_username(db, f"{provider_key}_{provider_uid}")
    local_display_name = (provider_display_name or provider_username or local_username).strip()[:100]
    oauth_username = (provider_username or "").strip()[:100]
    oauth_display_name = (provider_display_name or "").strip()[:200]

    user = User(
        username=local_username,
        display_name=local_display_name,
        password_hash=password_hash,
    )
    db.add(user)
    try:
        db.flush()
        account = OAuthAccount(
            user_id=user.id,
            provider=provider_key,
            provider_user_id=provider_uid,
            provider_username=oauth_username,
            provider_display_name=oauth_display_name,
        )
        db.add(account)
        db.commit()
    except IntegrityError:
        db.rollback()
        existing_user = get_user_by_oauth(db, provider_key, provider_uid)
        if existing_user:
            return existing_user
        raise OAuthAccountLinkError("failed to create oauth account")

    db.refresh(user)
    return user


def get_total_stats(db: Session) -> dict:
    from sqlalchemy import func
    result = db.query(
        func.count(Resource.id),
        func.coalesce(func.sum(Resource.downloads), 0),
        func.coalesce(func.sum(Resource.likes), 0) + func.coalesce(func.sum(Resource.favorites), 0),
    ).first()
    return {
        "total_resources": result[0] or 0,
        "total_downloads": result[1] or 0,
        "total_interactions": result[2] or 0,
    }


def get_total_resources(db: Session) -> int:
    return db.query(func.count(Resource.id)).scalar() or 0


def get_total_users(db: Session) -> int:
    return db.query(func.count(User.id)).scalar() or 0
