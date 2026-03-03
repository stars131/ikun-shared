# IKUN 资源分享网站

一个可直接部署的 `FastAPI` 资源分享站，支持上传和分享：

- 视频
- 歌曲
- 图片
- 表情包
- 其他资源（压缩包、文档等）

## 功能清单

- 首页资源展示（最新 / 热门）
- 关键词搜索（标题、描述、标签、作者）
- 分类筛选
- 资源详情页
- 文件上传 + 外链分享
- 下载统计
- JSON API（`/api/resources`）
- 健康检查（`/health`）

## 本地运行

1. 创建虚拟环境并安装依赖

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

2. 启动服务

```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

3. 访问页面

- 首页：`http://127.0.0.1:8000`
- 上传页：`http://127.0.0.1:8000/upload`
- API：`http://127.0.0.1:8000/api/resources`

## Docker 部署

### 方式一：Docker Compose（推荐）

```bash
docker compose up -d --build
```

停止服务：

```bash
docker compose down
```

### 方式二：纯 Docker

```bash
docker build -t ikun-share:latest .
docker run -d --name ikun-web -p 8000:8000 ^
  -e DATABASE_URL=sqlite:///./data/ikun.db ^
  -v %cd%\\data:/srv/ikun/data ^
  -v %cd%\\app\\uploads:/srv/ikun/app/uploads ^
  ikun-share:latest
```

## 目录结构

```text
ikun/
├─ app/
│  ├─ main.py
│  ├─ crud.py
│  ├─ models.py
│  ├─ database.py
│  ├─ templates/
│  ├─ static/
│  └─ uploads/
├─ data/                 # 运行时数据库目录（自动创建）
├─ Dockerfile
├─ docker-compose.yml
└─ requirements.txt
```

## 服务器部署建议

- 反向代理：`Nginx` → `ikun-web:8000`
- 域名证书：`Let's Encrypt`
- 上传目录与 `data/` 做持久化备份
- 生产环境建议加鉴权、审核、CDN、防盗链与对象存储

## 上传到 GitHub

在当前项目目录执行：

```bash
git init
git add .
git commit -m "feat: init ikun share website with docker deployment"
git branch -M main
git remote add origin <你的仓库地址>
git push -u origin main
```

如果你使用 GitHub CLI：

```bash
gh repo create <仓库名> --public --source . --remote origin --push
```

## 版权提示

请确保你上传或分享的资源具备合法授权，避免侵权内容传播。平台应提供侵权投诉入口和快速下架机制。
