import os
import uuid
from pathlib import Path
from typing import Optional

from fastapi import Depends, FastAPI, File, Form, HTTPException, Query, Request, UploadFile
from fastapi.responses import FileResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from . import crud, models, schemas
from .database import Base, engine, get_db

APP_NAME = "IKUN 资源分享站"
BASE_DIR = Path(__file__).resolve().parent
UPLOAD_DIR = BASE_DIR / "uploads"
DATA_DIR = BASE_DIR.parent / "data"

CATEGORIES = [
    ("video", "视频"),
    ("song", "歌曲"),
    ("image", "图片"),
    ("meme", "表情包"),
    ("other", "其他资源"),
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

app = FastAPI(title=APP_NAME, version="1.0.0")
app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")
app.mount("/uploads", StaticFiles(directory=str(UPLOAD_DIR)), name="uploads")
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))


def ensure_dirs():
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)


@app.on_event("startup")
def on_startup():
    ensure_dirs()
    Base.metadata.create_all(bind=engine)


@app.get("/")
def home(
    request: Request,
    q: str = Query(default="", description="搜索关键词"),
    category: str = Query(default="all"),
    sort: str = Query(default="latest"),
    db: Session = Depends(get_db),
):
    resources = crud.list_resources(db, query=q, category=category, sort=sort)
    return templates.TemplateResponse(
        "index.html",
        {
            "request": request,
            "title": APP_NAME,
            "resources": resources,
            "categories": CATEGORIES,
            "current_category": category,
            "current_sort": sort,
            "query": q,
        },
    )


@app.get("/upload")
def upload_page(request: Request):
    return templates.TemplateResponse(
        "upload.html",
        {"request": request, "title": f"上传资源 - {APP_NAME}", "categories": CATEGORIES},
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
    if category not in dict(CATEGORIES):
        return templates.TemplateResponse(
            "message.html",
            {
                "request": request,
                "title": "上传失败",
                "message": "分类非法，请重新选择。",
                "is_error": True,
            },
            status_code=400,
        )
    if not file and not external_url.strip():
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
        title=title.strip(),
        description=description.strip(),
        category=category,
        tags=tags.strip(),
        author=author.strip() or "匿名用户",
        external_url=external_url.strip(),
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
    return templates.TemplateResponse(
        "detail.html",
        {"request": request, "title": resource.title, "resource": resource, "categories": CATEGORIES},
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
            filename = local_path.name
            return FileResponse(path=str(local_path), filename=filename)
    raise HTTPException(status_code=404, detail="文件不存在")


@app.get("/api/resources", response_model=list[schemas.ResourceOut])
def api_resources(
    q: str = Query(default=""),
    category: str = Query(default="all"),
    sort: str = Query(default="latest"),
    db: Session = Depends(get_db),
):
    return crud.list_resources(db, query=q, category=category, sort=sort, limit=100)


@app.get("/health")
def health_check():
    return {"status": "ok", "service": APP_NAME}
