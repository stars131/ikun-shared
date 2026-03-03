# IKUN Shared

一个可直接部署的 `FastAPI` 资源分享网站，支持类似 GitHub Explore 的分类浏览、趋势榜和标签化管理。

## 主要功能

- GitHub 风格分类导航（视频 / 歌曲 / 图片 / 表情包 / 其他）
- 全站搜索（标题、描述、标签、作者）
- 趋势榜（24h / 7d / 30d / 全部）
- 首页趋势轮播卡片（可在设置中开关自动播放）
- 小红书帖子流模式（可在设置中切换默认展示）
- 上传文件或外链资源
- 每个文件都有标签（自动补齐分类、文件格式、外链标签）
- 资源详情页、下载统计、同分类推荐
- 开放 API：`/api/resources`、`/api/trending`

## 本地开发运行

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

访问：

- 首页：`http://127.0.0.1:8000`
- 趋势榜：`http://127.0.0.1:8000/trending`
- 上传：`http://127.0.0.1:8000/upload`
- 设置：`http://127.0.0.1:8000/settings`

## Docker 开发部署

```bash
docker compose up -d --build
docker compose down
```

## 生产部署配置（Nginx + Gunicorn）

已提供生产配置文件：

- `docker-compose.prod.yml`
- `deploy/nginx/default.conf`
- `.env.production.example`

启动步骤：

```bash
copy .env.production.example .env
docker compose -f docker-compose.prod.yml up -d --build
```

服务拓扑：

- `ikun-app`：`gunicorn + uvicorn worker`
- `ikun-nginx`：反向代理到 `ikun-app:8000`

## 项目结构

```text
ikun/
├─ app/
│  ├─ main.py
│  ├─ crud.py
│  ├─ models.py
│  ├─ schemas.py
│  ├─ database.py
│  ├─ templates/
│  ├─ static/
│  └─ uploads/
├─ deploy/nginx/default.conf
├─ Dockerfile
├─ docker-compose.yml
├─ docker-compose.prod.yml
└─ requirements.txt
```

## 推送到 GitHub

```bash
git add .
git commit -m "feat: add github-like categories, trending, prod deploy config"
git push
```

## 版权声明

请仅上传具备合法授权的内容，避免侵权传播。建议在生产环境增加举报、审核和下架流程。
