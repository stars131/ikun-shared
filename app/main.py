import os
import re
import secrets
import uuid
from pathlib import Path
from typing import Optional

from fastapi import Depends, FastAPI, File, Form, HTTPException, Query, Request, UploadFile
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy import inspect, text
from sqlalchemy.orm import Session

from . import crud, schemas
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

app = FastAPI(title=APP_NAME, version="1.2.0")
app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")
app.mount("/uploads", StaticFiles(directory=str(UPLOAD_DIR)), name="uploads")
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))


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


templates.env.globals["category_label"] = category_label


@app.on_event("startup")
def on_startup():
    ensure_dirs()
    Base.metadata.create_all(bind=engine)
    run_alembic_migrations()


@app.get("/")
def home(
    request: Request,
    q: str = Query(default="", description="搜索关键词"),
    category: str = Query(default="all"),
    sort: str = Query(default="latest"),
    view: str = Query(default="list"),
    db: Session = Depends(get_db),
):
    if category not in CATEGORY_LOOKUP:
        category = "all"
    if sort not in SORT_KEYS:
        sort = "latest"
    if view not in VIEW_KEYS:
        view = "list"

    resources = crud.list_resources(db, query=q, category=category, sort=sort)
    category_counts = crud.get_category_counts(db)
    category_counts["all"] = sum(category_counts.values())
    hot_tags = crud.list_hot_tags(db, limit=16)
    trending_preview = crud.list_trending(db, days=7, limit=6)
    current_category_meta = CATEGORY_LOOKUP.get(category, CATEGORY_LOOKUP["all"])

    return templates.TemplateResponse(
        "index.html",
        {
            "request": request,
            "title": APP_NAME,
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
        },
    )


@app.get("/categories/{category_key}")
def category_shortcut(category_key: str):
    if category_key not in CATEGORY_KEYS:
        raise HTTPException(status_code=404, detail="分类不存在")
    return RedirectResponse(url=f"/?category={category_key}", status_code=307)


@app.get("/settings")
def settings_page(request: Request):
    return templates.TemplateResponse(
        "settings.html",
        {"request": request, "title": f"设置 - {APP_NAME}", "view_items": VIEW_ITEMS},
    )


@app.get("/upload")
def upload_page(request: Request):
    return templates.TemplateResponse(
        "upload.html",
        {"request": request, "title": f"上传资源 - {APP_NAME}", "category_items": CATEGORY_ITEMS[1:]},
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
    resource = crud.get_resource(db, resource_id)
    if not resource:
        raise HTTPException(status_code=404, detail="资源不存在")
    related_resources = [
        item for item in crud.list_resources(db, category=resource.category, limit=8) if item.id != resource.id
    ][:4]
    return templates.TemplateResponse(
        "detail.html",
        {"request": request, "title": resource.title, "resource": resource, "related_resources": related_resources},
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
    current_period = TREND_LOOKUP.get(period, TREND_LOOKUP["7d"])
    resources = crud.list_trending(db, days=current_period["days"], limit=50)
    return templates.TemplateResponse(
        "trending.html",
        {
            "request": request,
            "title": f"趋势榜 - {APP_NAME}",
            "resources": resources,
            "period_items": TREND_PERIODS,
            "current_period": current_period["key"],
        },
    )


@app.post("/api/resources/{resource_id}/like")
def like_resource(request: Request, resource_id: int, db: Session = Depends(get_db)):
    resource = crud.get_resource(db, resource_id)
    if not resource:
        raise HTTPException(status_code=404, detail="资源不存在")
    client_token, is_new_cookie = get_or_create_client_token(request)
    accepted, updated = crud.register_reaction(db, resource, client_token, "like")
    response = JSONResponse(
        {
            "resource_id": updated.id,
            "likes": updated.likes,
            "favorites": updated.favorites,
            "accepted": accepted,
            "message": "点赞成功" if accepted else "今天已经点赞过了",
        }
    )
    if is_new_cookie:
        response.set_cookie(
            key=CLIENT_TOKEN_COOKIE,
            value=client_token,
            max_age=CLIENT_TOKEN_MAX_AGE,
            httponly=True,
            samesite="lax",
            secure=False,
        )
    return response


@app.post("/api/resources/{resource_id}/favorite")
def favorite_resource(request: Request, resource_id: int, db: Session = Depends(get_db)):
    resource = crud.get_resource(db, resource_id)
    if not resource:
        raise HTTPException(status_code=404, detail="资源不存在")
    client_token, is_new_cookie = get_or_create_client_token(request)
    accepted, updated = crud.register_reaction(db, resource, client_token, "favorite")
    response = JSONResponse(
        {
            "resource_id": updated.id,
            "likes": updated.likes,
            "favorites": updated.favorites,
            "accepted": accepted,
            "message": "收藏成功" if accepted else "今天已经收藏过了",
        }
    )
    if is_new_cookie:
        response.set_cookie(
            key=CLIENT_TOKEN_COOKIE,
            value=client_token,
            max_age=CLIENT_TOKEN_MAX_AGE,
            httponly=True,
            samesite="lax",
            secure=False,
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
