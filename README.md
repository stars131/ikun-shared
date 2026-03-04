# IKUN Shared

一个可部署的 `FastAPI` 资源分享网站，支持 GitHub 风格分类、趋势榜、小红书帖子流和互动功能。

## 主要功能

- GitHub 风格分类导航（视频 / 歌曲 / 图片 / 表情包 / 其他）
- 搜索与筛选（标题、描述、标签、作者）
- 趋势榜（24h / 7d / 30d / 全部）
- 首页趋势轮播（支持设置开关自动播放）
- 小红书帖子模式（支持设置为默认视图）
- 帖子封面按比例自适应裁剪（横图 / 方图 / 竖图）
- 点赞与收藏（实时计数）
- 点赞/收藏去重（同一设备每天同资源同动作仅一次）
- 上传文件或外链，自动补齐文件标签

## 本地开发

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
alembic upgrade head
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

访问地址：

- 首页：`http://127.0.0.1:8000`
- 趋势榜：`http://127.0.0.1:8000/trending`
- 上传页：`http://127.0.0.1:8000/upload`
- 设置页：`http://127.0.0.1:8000/settings`

## 数据库迁移（Alembic）

```bash
alembic upgrade head
```

当前迁移文件：`alembic/versions/20260304_0001_reactions_migration.py`

## Docker 开发部署

```bash
docker compose up -d --build
docker compose down
```

容器启动会自动执行：

```bash
alembic upgrade head
```

## 生产部署（Nginx + Gunicorn）

已提供：

- `docker-compose.prod.yml`
- `deploy/nginx/default.conf`
- `.env.production.example`

启动：

```bash
copy .env.production.example .env
docker compose -f docker-compose.prod.yml up -d --build
```

## 项目结构

```text
ikun/
├─ app/
│  ├─ main.py
│  ├─ models.py
│  ├─ crud.py
│  ├─ schemas.py
│  ├─ templates/
│  ├─ static/
│  │  └─ js/
│  └─ uploads/
├─ alembic/
│  └─ versions/
├─ alembic.ini
├─ deploy/nginx/default.conf
├─ Dockerfile
├─ docker-compose.yml
├─ docker-compose.prod.yml
└─ requirements.txt
```

## 推送到 GitHub

```bash
git add .
git commit -m "feat: improve reactions, migrations, and UX"
git push
```

## 版权说明

请仅上传合法授权内容，建议生产环境开启举报、审核、下架流程。
