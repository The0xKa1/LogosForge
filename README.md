# LogosForge

LogosForge 是一个面向“多教材知识整合”的全栈智能体项目。它可以加载多本教材，抽取章节与知识点，构建教材知识图谱，识别跨教材的重复、互补与缺失，并通过 RAG 问答和教师反馈迭代整合方案。

项目来自 AI 全栈黑客松场景，当前重点是可演示、可追溯、可降级运行：即使没有 LLM key 或 embedding 服务异常，也能通过 fallback 完成核心流程。

## 在线演示

- 前端工作台：https://logosforge.the0xka1.cc
- 健康检查：https://logosforge.the0xka1.cc/api/health
- 生产 API 采用同源 `/api/*`，由 Vercel rewrite 到阿里云后端 80 端口。

> 教材 PDF、真实 `.env`、本地 ChromaDB、运行态 `state.json` 不进入仓库。

## 核心能力

- 多格式教材加载：PDF / Markdown / TXT / DOCX
- 教材解析：章节识别、有效正文统计、页码与教材元数据保留
- 知识图谱：按章节抽取知识点，生成 `prerequisite / contains / applies_to / parallel` 等关系
- 跨教材整合：生成 `merge / keep / remove` 决策，保留理由与置信度
- 30% 压缩：按“整合正文字符数 / 原始有效正文字符数”计算压缩比
- RAG 问答：ChromaDB + BGE embedding 优先，词项检索 fallback，答案带引用
- 教师对话：教师反馈可更新整合决策
- 报告生成：输出 `report/整合报告.md`
- 演示数据：服务器已导入医学教材数据，当前 summary 接口可快速返回教材列表与统计

## 技术栈

| 层 | 技术 |
| --- | --- |
| Frontend | Next.js 14, React 18, TypeScript, Cytoscape.js |
| Backend | FastAPI, Pydantic, PyMuPDF, python-docx |
| Retrieval | ChromaDB, sentence-transformers, BGE |
| LLM | OpenAI-compatible Chat Completions API |
| State | JSON state store with Postgres JSONB-compatible repository shape |
| Deploy | Vercel frontend, Docker Compose backend on Aliyun ECS, Nginx reverse proxy |

## 项目结构

```text
.
├── backend/                 # FastAPI backend
│   ├── app/
│   │   ├── main.py          # API routes
│   │   ├── models.py        # Pydantic domain models
│   │   ├── storage.py       # JSON state store
│   │   └── services/        # parser / graph / rag / report
│   └── scripts/
│       └── import_medical_rag.py
├── frontend/                # Next.js TypeScript frontend
│   ├── app/                 # / and /graph pages
│   ├── components/
│   ├── lib/api.ts
│   └── types/domain.ts
├── docs/                    # requirement/design/API/handoff docs
├── report/                  # generated integration report
├── docker-compose.prod.yml  # Aliyun backend deployment
└── nginx.conf
```

## 本地运行

### 1. 后端

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r backend/requirements.txt
cp backend/.env.example backend/.env

npm run dev:backend
```

后端默认运行在：

```text
http://localhost:8000
```

### 2. 前端

```bash
cd frontend
npm install
npm run dev
```

前端默认运行在：

```text
http://localhost:3000
```

本地开发时可以指定后端地址：

```bash
NEXT_PUBLIC_API_BASE=http://localhost:8000 npm run dev
```

生产构建中前端默认使用同源 `/api/*`，不会把公网后端地址写进浏览器 JS。

## 环境变量

`backend/.env`：

```bash
LLM_BASE_URL=https://api.openai.com/v1
LLM_API_KEY=
LLM_MODEL=gpt-4o
RAG_TEMPERATURE=0.2
RAG_MAX_TOKENS=2000
RAG_TIMEOUT_SECONDS=45

EMBEDDING_MODEL=BAAI/bge-large-zh-v1.5
CHROMA_DB_DIR=backend/chroma_db
DATA_DIR=backend
UPLOAD_DIR=uploads
```

生产后端额外使用：

```bash
CORS_ORIGINS=https://logosforge.the0xka1.cc
```

前端 Vercel 可选环境变量：

```bash
BACKEND_ORIGIN=http://116.62.86.237
```

如果不设置，`frontend/next.config.mjs` 默认将 `/api/*` rewrite 到 `http://116.62.86.237/api/*`。

## 关键 API

| Method | Path | 用途 |
| --- | --- | --- |
| GET | `/api/health` | 健康检查 |
| GET | `/api/state/summary` | 首页轻量状态，避免返回章节全文和 chunks |
| GET | `/api/state` | 全量状态导出，调试用途，真实数据下体积很大 |
| POST | `/api/textbooks/upload` | 上传教材 |
| POST | `/api/textbooks/parse` | 解析教材 |
| POST | `/api/graph/build` | 构建单本/多本教材图谱 |
| POST | `/api/graph/merge` | 跨教材整合 |
| POST | `/api/rag/index` | 建立 RAG 索引 |
| GET | `/api/rag/status` | RAG 索引状态 |
| POST | `/api/rag/query` | 带引用问答 |
| POST | `/api/teacher/chat` | 教师反馈对话 |
| POST | `/api/report/generate` | 生成整合报告 |

## 复用 medical-rag 数据

如果本机已有 `/Users/zhangjinkai/textbooks/medical-rag/chroma_db/chroma.sqlite3`，可以导入旧项目的医学教材 chunks：

```bash
python3 -m backend.scripts.import_medical_rag
```

脚本会：

- 从旧 Chroma sqlite 读取教材 chunks
- 重建本项目 `state.json`
- 检测教材来源
- 使用当前 embedding 模型重建本项目 Chroma collection
- 显示 embedding 进度条

## 部署说明

### 前端 Vercel

前端部署目录为 `frontend/`。生产环境使用 Next rewrite：

```text
Browser -> https://logosforge.the0xka1.cc/api/*
Vercel rewrite -> http://116.62.86.237/api/*
Nginx -> FastAPI backend
```

这样可以复用服务器 80 端口，并避免 HTTPS 页面请求 HTTP `:8000` 造成 mixed content。

### 后端 Aliyun ECS

```bash
docker compose -f docker-compose.prod.yml up -d --build
```

Nginx 暴露 80/443，后端容器内部运行 FastAPI。当前线上健康检查：

```bash
curl https://logosforge.the0xka1.cc/api/health
```

期望返回：

```json
{"status":"ok"}
```

## 验证命令

```bash
python3 -m compileall backend/app
npm --prefix frontend run typecheck
npm --prefix frontend run build
```

线上轻量状态检查：

```bash
curl https://logosforge.the0xka1.cc/api/state/summary
```

## 当前限制

- 当前数据层仍是 JSON state store，接口形态按未来 Postgres JSONB repository 设计。
- `/api/state` 是全量调试接口，真实教材导入后可能超过 20MB；页面应使用 `/api/state/summary`。
- 完整图谱构建依赖 LLM 与教材规模，大教材会耗时较长。
- BGE embedding 首次加载需要模型缓存；生产镜像已尽量预置模型。
- 本项目不会提交教材 PDF、真实 API key、ChromaDB 数据或运行态 state。

## License

Hackathon prototype. Add a formal license before production or public reuse.
