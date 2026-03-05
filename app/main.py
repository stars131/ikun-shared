import hmac
import json
import math
import os
import re
import secrets
import uuid
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Optional
from urllib import parse as urllib_parse
from urllib import request as urllib_request

from fastapi import Depends, FastAPI, File, Form, HTTPException, Query, Request, UploadFile
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy import inspect, text
from sqlalchemy.orm import Session

from . import crud, schemas
from .auth import (
    SESSION_COOKIE,
    SESSION_MAX_AGE,
    create_session_cookie,
    get_current_user,
    hash_password,
    needs_password_rehash,
    verify_password,
)
from .database import Base, engine, get_db
from .models import CATEGORY_LABELS

APP_NAME = "IKUN Shared"
BASE_DIR = Path(__file__).resolve().parent
UPLOAD_DIR = BASE_DIR / "uploads"
DATA_DIR = BASE_DIR.parent / "data"

CATEGORY_ITEMS = [
    {"key": "all", "label": "全部", "icon": "📁", "description": "全部资源"},
    {"key": "video", "label": "视频", "icon": "🎬", "description": "演出、剪辑、鬼畜视频"},
    {"key": "song", "label": "歌曲", "icon": "🎵", "description": "音频、伴奏、翻唱作品"},
    {"key": "image", "label": "图片", "icon": "🖼️", "description": "海报、截图、摄影图"},
    {"key": "meme", "label": "表情包", "icon": "😂", "description": "梗图、表情包、贴纸"},
    {"key": "other", "label": "其他", "icon": "📦", "description": "压缩包、文档、素材"},
]

SORT_ITEMS = [
    {"key": "latest", "label": "最近更新"},
    {"key": "popular", "label": "下载最多"},
]

VIEW_ITEMS = [
    {"key": "list", "label": "GitHub列表"},
    {"key": "post", "label": "小红书帖子"},
]

TREND_PERIODS = [
    {"key": "24h", "label": "24 小时", "days": 1},
    {"key": "7d", "label": "7 天", "days": 7},
    {"key": "30d", "label": "30 天", "days": 30},
    {"key": "all", "label": "全部时间", "days": None},
]

ALLOWED_EXTENSIONS = {
    ".mp4",
    ".mov",
    ".avi",
    ".mkv",
    ".mp3",
    ".wav",
    ".flac",
    ".jpg",
    ".jpeg",
    ".png",
    ".gif",
    ".webp",
    ".zip",
    ".rar",
    ".7z",
    ".pdf",
}

CATEGORY_KEYS = {item["key"] for item in CATEGORY_ITEMS if item["key"] != "all"}
CATEGORY_LOOKUP = {item["key"]: item for item in CATEGORY_ITEMS}
TREND_LOOKUP = {item["key"]: item for item in TREND_PERIODS}
SORT_KEYS = {item["key"] for item in SORT_ITEMS}
VIEW_KEYS = {item["key"] for item in VIEW_ITEMS}
CLIENT_TOKEN_COOKIE = "ikun_client_token"
CLIENT_TOKEN_MAX_AGE = 60 * 60 * 24 * 365
COOKIE_SECURE_MODE = os.getenv("COOKIE_SECURE", "auto").strip().lower()
OAUTH_STATE_COOKIE = "ikun_oauth_state"
OAUTH_STATE_MAX_AGE = 60 * 10
LINUXDO_PROVIDER = "linuxdo"
LINUXDO_OAUTH_ENABLED = os.getenv("LINUXDO_OAUTH_ENABLED", "false").strip().lower() in {"1", "true", "yes", "on"}
LINUXDO_CLIENT_ID = os.getenv("LINUXDO_CLIENT_ID", "").strip()
LINUXDO_CLIENT_SECRET = os.getenv("LINUXDO_CLIENT_SECRET", "").strip()
LINUXDO_REDIRECT_URI = os.getenv("LINUXDO_REDIRECT_URI", "").strip()
LINUXDO_AUTHORIZE_URL = os.getenv("LINUXDO_AUTHORIZE_URL", "https://connect.linux.do/oauth2/authorize").strip()
LINUXDO_TOKEN_URL = os.getenv("LINUXDO_TOKEN_URL", "https://connect.linux.do/oauth2/token").strip()
LINUXDO_USERINFO_URL = os.getenv("LINUXDO_USERINFO_URL", "https://connect.linux.do/api/user").strip()


def ensure_dirs():
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)


def ensure_schema_fallback():
    inspector = inspect(engine)
    if "resources" in inspector.get_table_names():
        column_names = {column["name"] for column in inspector.get_columns("resources")}
        with engine.begin() as connection:
            if "likes" not in column_names:
                connection.execute(text("ALTER TABLE resources ADD COLUMN likes INTEGER DEFAULT 0"))
            if "favorites" not in column_names:
                connection.execute(text("ALTER TABLE resources ADD COLUMN favorites INTEGER DEFAULT 0"))
    Base.metadata.tables["resource_reactions"].create(bind=engine, checkfirst=True)
    Base.metadata.tables["users"].create(bind=engine, checkfirst=True)
    Base.metadata.tables["oauth_accounts"].create(bind=engine, checkfirst=True)


def run_alembic_migrations():
    try:
        from alembic import command as alembic_command
        from alembic.config import Config
    except Exception:
        ensure_schema_fallback()
        return

    try:
        config = Config(str(BASE_DIR.parent / "alembic.ini"))
        config.set_main_option("script_location", str(BASE_DIR.parent / "alembic"))
        config.set_main_option("sqlalchemy.url", os.getenv("DATABASE_URL", "sqlite:///./data/ikun.db"))
        alembic_command.upgrade(config, "head")
    except Exception:
        ensure_schema_fallback()


def get_or_create_client_token(request: Request) -> tuple[str, bool]:
    token = request.cookies.get(CLIENT_TOKEN_COOKIE, "").strip()
    if token and len(token) >= 16:
        return token[:64], False
    return secrets.token_hex(16), True


def should_use_secure_cookie(request: Request) -> bool:
    if COOKIE_SECURE_MODE in {"1", "true", "yes", "on"}:
        return True
    if COOKIE_SECURE_MODE in {"0", "false", "no", "off"}:
        return False
    return get_request_scheme(request) == "https"


def get_request_scheme(request: Request) -> str:
    forwarded_proto = request.headers.get("x-forwarded-proto", "")
    if forwarded_proto:
        return forwarded_proto.split(",")[0].strip().lower() or request.url.scheme
    return request.url.scheme


def get_request_host(request: Request) -> str:
    forwarded_host = request.headers.get("x-forwarded-host", "")
    if forwarded_host:
        host = forwarded_host.split(",")[0].strip()
        if host:
            return host
    host_header = request.headers.get("host", "").strip()
    if host_header:
        return host_header
    return request.url.netloc


def is_linuxdo_oauth_ready() -> bool:
    return LINUXDO_OAUTH_ENABLED and bool(LINUXDO_CLIENT_ID and LINUXDO_CLIENT_SECRET)


def build_linuxdo_redirect_uri(request: Request) -> str:
    if LINUXDO_REDIRECT_URI:
        return LINUXDO_REDIRECT_URI
    return f"{get_request_scheme(request)}://{get_request_host(request)}{request.url_for('linuxdo_callback').path}"


def category_label(category_key: str) -> str:
    return CATEGORY_LABELS.get(category_key, category_key)


def split_tags(raw_tags: str) -> list[str]:
    values = re.split(r"[,\s，#]+", raw_tags or "")
    tags: list[str] = []
    seen = set()
    for value in values:
        tag = value.strip()
        if not tag:
            continue
        lowered = tag.lower()
        if lowered in seen:
            continue
        seen.add(lowered)
        tags.append(tag)
    return tags


def normalize_tags(raw_tags: str, category: str, file_name: str = "", external: bool = False) -> str:
    tags = split_tags(raw_tags)
    default_tags = [category_label(category)]
    suffix = Path(file_name).suffix.lower().replace(".", "").strip()
    if suffix:
        default_tags.append(suffix)
    if external:
        default_tags.append("外链")
    for tag in default_tags:
        if tag.lower() not in {existing.lower() for existing in tags}:
            tags.append(tag)
    return ", ".join(tags[:8])


def render_login_page(
    request: Request,
    *,
    title: str,
    error: Optional[str],
    active_tab: str = "login",
    status_code: int = 200,
):
    return templates.TemplateResponse(
        "login.html",
        {
            "request": request,
            "title": title,
            "error": error,
            "active_tab": active_tab,
            "linuxdo_oauth_enabled": is_linuxdo_oauth_ready(),
        },
        status_code=status_code,
    )


def exchange_linuxdo_access_token(code: str, redirect_uri: str) -> str:
    payload = urllib_parse.urlencode(
        {
            "client_id": LINUXDO_CLIENT_ID,
            "client_secret": LINUXDO_CLIENT_SECRET,
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": redirect_uri,
        }
    ).encode("utf-8")
    req = urllib_request.Request(LINUXDO_TOKEN_URL, data=payload, method="POST")
    req.add_header("Content-Type", "application/x-www-form-urlencoded")
    req.add_header("Accept", "application/json")
    with urllib_request.urlopen(req, timeout=10) as resp:
        raw = json.loads(resp.read().decode("utf-8"))
    access_token = str(raw.get("access_token", "")).strip()
    if not access_token:
        raise ValueError("linuxdo access token missing")
    return access_token


def fetch_linuxdo_profile(access_token: str) -> tuple[str, str, str]:
    req = urllib_request.Request(LINUXDO_USERINFO_URL, method="GET")
    req.add_header("Accept", "application/json")
    req.add_header("Authorization", f"Bearer {access_token}")
    with urllib_request.urlopen(req, timeout=10) as resp:
        raw = json.loads(resp.read().decode("utf-8"))
    data = raw.get("data") or {}
    attrs = data.get("attributes") or {}
    provider_user_id = str(data.get("id") or "").strip()
    provider_username = str(attrs.get("username") or "").strip()
    provider_display_name = str(attrs.get("name") or "").strip() or provider_username
    if not provider_user_id or not provider_username:
        raise ValueError("linuxdo user profile missing required fields")
    return provider_user_id, provider_username, provider_display_name


@asynccontextmanager
async def lifespan(app):
    ensure_dirs()
    Base.metadata.create_all(bind=engine)
    run_alembic_migrations()
    yield


app = FastAPI(title=APP_NAME, version="2.0.0", lifespan=lifespan)
app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")
app.mount("/uploads", StaticFiles(directory=str(UPLOAD_DIR)), name="uploads")
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))
templates.env.globals["category_label"] = category_label


# ---------------------------------------------------------------------------
# Landing Page
# ---------------------------------------------------------------------------


@app.get("/")
def landing_page(request: Request, db: Session = Depends(get_db)):
    current_user = get_current_user(request, db)
    stats = crud.get_total_stats(db)
    category_counts = crud.get_category_counts(db)
    return templates.TemplateResponse(
        "landing.html",
        {
            "request": request,
            "title": APP_NAME,
            "current_user": current_user,
            "stats": stats,
            "category_items": CATEGORY_ITEMS[1:],
            "category_counts": category_counts,
        },
    )


# ---------------------------------------------------------------------------
# Auth routes
# ---------------------------------------------------------------------------


@app.get("/login")
def login_page(request: Request, db: Session = Depends(get_db)):
    current_user = get_current_user(request, db)
    if current_user:
        return RedirectResponse(url="/browse", status_code=303)
    return render_login_page(
        request,
        title=f"登录 - {APP_NAME}",
        error=None,
        active_tab="login",
    )


@app.post("/login")
def login_submit(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
    db: Session = Depends(get_db),
):
    user = crud.get_user_by_username(db, username.strip())
    if not user or not verify_password(password, user.password_hash):
        return render_login_page(
            request,
            title=f"登录 - {APP_NAME}",
            error="用户名或密码错误",
            active_tab="login",
            status_code=400,
        )
    if needs_password_rehash(user.password_hash):
        try:
            user.password_hash = hash_password(password)
            db.add(user)
            db.commit()
        except Exception:
            db.rollback()
    response = RedirectResponse(url="/browse", status_code=303)
    response.set_cookie(
        key=SESSION_COOKIE,
        value=create_session_cookie(user.id),
        max_age=SESSION_MAX_AGE,
        httponly=True,
        samesite="lax",
        secure=should_use_secure_cookie(request),
    )
    return response


@app.get("/auth/linuxdo")
def linuxdo_login_start(request: Request):
    if not is_linuxdo_oauth_ready():
        return render_login_page(
            request,
            title=f"登录 - {APP_NAME}",
            error="LinuxDO 登录未启用，请联系管理员配置。",
            active_tab="login",
            status_code=503,
        )

    state = secrets.token_urlsafe(24)
    redirect_uri = build_linuxdo_redirect_uri(request)
    params = urllib_parse.urlencode(
        {
            "client_id": LINUXDO_CLIENT_ID,
            "response_type": "code",
            "redirect_uri": redirect_uri,
            "state": state,
        }
    )
    response = RedirectResponse(url=f"{LINUXDO_AUTHORIZE_URL}?{params}", status_code=302)
    response.set_cookie(
        key=OAUTH_STATE_COOKIE,
        value=state,
        max_age=OAUTH_STATE_MAX_AGE,
        httponly=True,
        samesite="lax",
        secure=should_use_secure_cookie(request),
    )
    return response


@app.get("/auth/linuxdo/callback", name="linuxdo_callback")
def linuxdo_callback(
    request: Request,
    code: str = Query(default=""),
    state: str = Query(default=""),
    error: str = Query(default=""),
    db: Session = Depends(get_db),
):
    if not is_linuxdo_oauth_ready():
        return render_login_page(
            request,
            title=f"登录 - {APP_NAME}",
            error="LinuxDO 登录未启用，请联系管理员配置。",
            active_tab="login",
            status_code=503,
        )

    if error:
        return render_login_page(
            request,
            title=f"登录 - {APP_NAME}",
            error=f"LinuxDO 登录失败：{error}",
            active_tab="login",
            status_code=400,
        )

    state_cookie = request.cookies.get(OAUTH_STATE_COOKIE, "").strip()
    if not code or not state_cookie or not state or not hmac.compare_digest(state_cookie, state):
        return render_login_page(
            request,
            title=f"登录 - {APP_NAME}",
            error="LinuxDO 登录状态校验失败，请重试。",
            active_tab="login",
            status_code=400,
        )

    try:
        redirect_uri = build_linuxdo_redirect_uri(request)
        access_token = exchange_linuxdo_access_token(code, redirect_uri)
        provider_user_id, provider_username, provider_display_name = fetch_linuxdo_profile(access_token)
    except Exception:
        return render_login_page(
            request,
            title=f"登录 - {APP_NAME}",
            error="LinuxDO 授权失败，请稍后重试。",
            active_tab="login",
            status_code=400,
        )

    try:
        user = crud.get_or_create_user_by_oauth(
            db,
            provider=LINUXDO_PROVIDER,
            provider_user_id=provider_user_id,
            provider_username=provider_username,
            provider_display_name=provider_display_name,
            password_hash=hash_password(secrets.token_urlsafe(24)),
        )
    except crud.OAuthAccountLinkError:
        return render_login_page(
            request,
            title=f"登录 - {APP_NAME}",
            error="LinuxDO 账号绑定失败，请稍后重试。",
            active_tab="login",
            status_code=500,
        )

    response = RedirectResponse(url="/browse", status_code=303)
    response.delete_cookie(
        key=OAUTH_STATE_COOKIE,
        httponly=True,
        samesite="lax",
        secure=should_use_secure_cookie(request),
    )
    response.set_cookie(
        key=SESSION_COOKIE,
        value=create_session_cookie(user.id),
        max_age=SESSION_MAX_AGE,
        httponly=True,
        samesite="lax",
        secure=should_use_secure_cookie(request),
    )
    return response


@app.post("/register")
def register_submit(
    request: Request,
    username: str = Form(...),
    display_name: str = Form(default=""),
    password: str = Form(...),
    password_confirm: str = Form(...),
    db: Session = Depends(get_db),
):
    clean_username = username.strip()
    clean_display = display_name.strip()
    errors = []
    if len(clean_username) < 3 or len(clean_username) > 30:
        errors.append("用户名长度需要 3-30 个字符")
    if not re.match(r"^[a-zA-Z0-9_\u4e00-\u9fff]+$", clean_username):
        errors.append("用户名只能包含字母、数字、下划线或中文")
    if len(password) < 6:
        errors.append("密码长度至少 6 个字符")
    if password != password_confirm:
        errors.append("两次输入的密码不一致")
    if not errors and crud.get_user_by_username(db, clean_username):
        errors.append("该用户名已被注册")

    if errors:
        return render_login_page(
            request,
            title=f"注册 - {APP_NAME}",
            error="；".join(errors),
            active_tab="register",
            status_code=400,
        )

    try:
        user = crud.create_user(db, clean_username, clean_display, hash_password(password))
    except crud.UsernameExistsError:
        return render_login_page(
            request,
            title=f"注册 - {APP_NAME}",
            error="该用户名已被注册",
            active_tab="register",
            status_code=400,
        )
    response = RedirectResponse(url="/browse", status_code=303)
    response.set_cookie(
        key=SESSION_COOKIE,
        value=create_session_cookie(user.id),
        max_age=SESSION_MAX_AGE,
        httponly=True,
        samesite="lax",
        secure=should_use_secure_cookie(request),
    )
    return response


@app.post("/logout")
def logout_submit(request: Request):
    response = RedirectResponse(url="/", status_code=303)
    response.delete_cookie(
        key=SESSION_COOKIE,
        httponly=True,
        samesite="lax",
        secure=should_use_secure_cookie(request),
    )
    return response


# ---------------------------------------------------------------------------
# Browse (resource browsing, formerly at /)
# ---------------------------------------------------------------------------


@app.get("/browse")
def browse_page(
    request: Request,
    q: str = Query(default="", description="搜索关键词"),
    category: str = Query(default="all"),
    sort: str = Query(default="latest"),
    view: str = Query(default="list"),
    page: int = Query(default=1, ge=1),
    db: Session = Depends(get_db),
):
    current_user = get_current_user(request, db)
    if category not in CATEGORY_LOOKUP:
        category = "all"
    if sort not in SORT_KEYS:
        sort = "latest"
    if view not in VIEW_KEYS:
        view = "list"

    per_page = 20
    resources, total = crud.list_resources_paginated(
        db, query=q, category=category, sort=sort, page=page, per_page=per_page
    )
    total_pages = max(1, math.ceil(total / per_page))
    if page > total_pages:
        page = total_pages
    category_counts = crud.get_category_counts(db)
    category_counts["all"] = sum(category_counts.values())
    hot_tags = crud.list_hot_tags(db, limit=16)
    trending_preview = crud.list_trending(db, days=7, limit=6)
    current_category_meta = CATEGORY_LOOKUP.get(category, CATEGORY_LOOKUP["all"])

    return templates.TemplateResponse(
        "browse.html",
        {
            "request": request,
            "title": APP_NAME,
            "current_user": current_user,
            "resources": resources,
            "category_items": CATEGORY_ITEMS,
            "sort_items": SORT_ITEMS,
            "view_items": VIEW_ITEMS,
            "current_category": category,
            "current_sort": sort,
            "current_view": view,
            "query": q,
            "category_counts": category_counts,
            "hot_tags": hot_tags,
            "trending_preview": trending_preview,
            "current_category_meta": current_category_meta,
            "page": page,
            "total_pages": total_pages,
            "total": total,
        },
    )


@app.get("/categories/{category_key}")
def category_shortcut(category_key: str):
    if category_key not in CATEGORY_KEYS:
        raise HTTPException(status_code=404, detail="分类不存在")
    return RedirectResponse(url=f"/browse?category={category_key}", status_code=307)


@app.get("/settings")
def settings_page(request: Request, db: Session = Depends(get_db)):
    current_user = get_current_user(request, db)
    return templates.TemplateResponse(
        "settings.html",
        {"request": request, "title": f"设置 - {APP_NAME}", "view_items": VIEW_ITEMS, "current_user": current_user},
    )


@app.get("/upload")
def upload_page(request: Request, db: Session = Depends(get_db)):
    current_user = get_current_user(request, db)
    return templates.TemplateResponse(
        "upload.html",
        {
            "request": request,
            "title": f"上传资源 - {APP_NAME}",
            "category_items": CATEGORY_ITEMS[1:],
            "current_user": current_user,
        },
    )


def _save_upload_file(upload_file: UploadFile, target_dir: Path) -> str:
    original_name = upload_file.filename or ""
    extension = Path(original_name).suffix.lower()
    if extension and extension not in ALLOWED_EXTENSIONS:
        raise HTTPException(status_code=400, detail=f"不支持的文件类型: {extension}")
    safe_filename = f"{uuid.uuid4().hex}{extension}"
    target_path = target_dir / safe_filename
    with target_path.open("wb") as buffer:
        while True:
            chunk = upload_file.file.read(1024 * 1024)
            if not chunk:
                break
            buffer.write(chunk)
    return f"/uploads/{safe_filename}"


@app.post("/upload")
def upload_resource(
    request: Request,
    title: str = Form(...),
    description: str = Form(default=""),
    category: str = Form(...),
    tags: str = Form(default=""),
    author: str = Form(default="匿名用户"),
    external_url: str = Form(default=""),
    file: Optional[UploadFile] = File(default=None),
    preview_image: Optional[UploadFile] = File(default=None),
    db: Session = Depends(get_db),
):
    safe_title = title.strip()
    if not safe_title:
        return templates.TemplateResponse(
            "message.html",
            {"request": request, "title": "上传失败", "message": "标题不能为空。", "is_error": True},
            status_code=400,
        )
    if category not in CATEGORY_KEYS:
        return templates.TemplateResponse(
            "message.html",
            {"request": request, "title": "上传失败", "message": "分类非法，请重新选择。", "is_error": True},
            status_code=400,
        )
    normalized_url = external_url.strip()
    if normalized_url and not normalized_url.startswith(("http://", "https://")):
        return templates.TemplateResponse(
            "message.html",
            {
                "request": request,
                "title": "上传失败",
                "message": "外链地址必须以 http:// 或 https:// 开头。",
                "is_error": True,
            },
            status_code=400,
        )
    if not file and not normalized_url:
        return templates.TemplateResponse(
            "message.html",
            {
                "request": request,
                "title": "上传失败",
                "message": "请至少上传一个文件，或填写外链地址。",
                "is_error": True,
            },
            status_code=400,
        )

    file_path = ""
    preview_path = ""
    source_file_name = file.filename if file else ""
    try:
        if file:
            file_path = _save_upload_file(file, UPLOAD_DIR)
        if preview_image:
            preview_path = _save_upload_file(preview_image, UPLOAD_DIR)
    finally:
        if file:
            file.file.close()
        if preview_image:
            preview_image.file.close()

    if category in {"image", "meme"} and file_path and not preview_path:
        preview_path = file_path

    payload = schemas.ResourceCreate(
        title=safe_title,
        description=description.strip(),
        category=category,
        tags=normalize_tags(tags, category, source_file_name, external=bool(normalized_url)),
        author=author.strip() or "匿名用户",
        external_url=normalized_url,
        file_path=file_path,
        preview_image=preview_path,
    )
    resource = crud.create_resource(db, payload)
    return RedirectResponse(url=f"/resource/{resource.id}", status_code=303)


@app.get("/resource/{resource_id}")
def resource_detail(request: Request, resource_id: int, db: Session = Depends(get_db)):
    current_user = get_current_user(request, db)
    resource = crud.get_resource(db, resource_id)
    if not resource:
        raise HTTPException(status_code=404, detail="资源不存在")
    related_resources = [
        item for item in crud.list_resources(db, category=resource.category, limit=8) if item.id != resource.id
    ][:4]
    return templates.TemplateResponse(
        "detail.html",
        {
            "request": request,
            "title": resource.title,
            "current_user": current_user,
            "resource": resource,
            "related_resources": related_resources,
            "category_lookup": CATEGORY_LOOKUP,
        },
    )


@app.get("/download/{resource_id}")
def download_resource(resource_id: int, db: Session = Depends(get_db)):
    resource = crud.get_resource(db, resource_id)
    if not resource:
        raise HTTPException(status_code=404, detail="资源不存在")
    crud.increase_download(db, resource)

    if resource.external_url:
        return RedirectResponse(url=resource.external_url, status_code=307)
    if resource.file_path:
        local_path = BASE_DIR / resource.file_path.lstrip("/").replace("/", os.sep)
        if local_path.exists():
            return FileResponse(path=str(local_path), filename=local_path.name)
    raise HTTPException(status_code=404, detail="文件不存在")


@app.get("/trending")
def trending_page(
    request: Request,
    period: str = Query(default="7d"),
    db: Session = Depends(get_db),
):
    current_user = get_current_user(request, db)
    current_period = TREND_LOOKUP.get(period, TREND_LOOKUP["7d"])
    resources = crud.list_trending(db, days=current_period["days"], limit=50)
    return templates.TemplateResponse(
        "trending.html",
        {
            "request": request,
            "title": f"趋势榜 - {APP_NAME}",
            "current_user": current_user,
            "resources": resources,
            "period_items": TREND_PERIODS,
            "current_period": current_period["key"],
        },
    )


ACTION_LABELS = {"like": ("点赞成功", "今天已经点赞过了"), "favorite": ("收藏成功", "今天已经收藏过了")}


@app.post("/api/resources/{resource_id}/{action}")
def react_to_resource(request: Request, resource_id: int, action: str, db: Session = Depends(get_db)):
    if action not in ACTION_LABELS:
        raise HTTPException(status_code=400, detail="不支持的操作")
    resource = crud.get_resource(db, resource_id)
    if not resource:
        raise HTTPException(status_code=404, detail="资源不存在")
    client_token, is_new_cookie = get_or_create_client_token(request)
    accepted, updated = crud.register_reaction(db, resource, client_token, action)
    success_msg, duplicate_msg = ACTION_LABELS[action]
    response = JSONResponse(
        {
            "resource_id": updated.id,
            "likes": updated.likes,
            "favorites": updated.favorites,
            "accepted": accepted,
            "message": success_msg if accepted else duplicate_msg,
        }
    )
    if is_new_cookie:
        response.set_cookie(
            key=CLIENT_TOKEN_COOKIE,
            value=client_token,
            max_age=CLIENT_TOKEN_MAX_AGE,
            httponly=True,
            samesite="lax",
            secure=should_use_secure_cookie(request),
        )
    return response


@app.get("/api/resources", response_model=list[schemas.ResourceOut])
def api_resources(
    q: str = Query(default=""),
    category: str = Query(default="all"),
    sort: str = Query(default="latest"),
    db: Session = Depends(get_db),
):
    return crud.list_resources(db, query=q, category=category, sort=sort, limit=100)


@app.get("/api/trending", response_model=list[schemas.ResourceOut])
def api_trending(
    period: str = Query(default="7d"),
    db: Session = Depends(get_db),
):
    days = TREND_LOOKUP.get(period, TREND_LOOKUP["7d"])["days"]
    return crud.list_trending(db, days=days, limit=50)


@app.get("/health")
def health_check():
    return {"status": "ok", "service": APP_NAME}
