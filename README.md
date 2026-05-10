# 学科知识整合智能体

面向 AI 全栈黑客松的多教材知识整合系统：上传多本教材，解析章节，构建可视化知识图谱，跨教材识别重复/互补/缺失，压缩生成不超过原始有效正文 30% 的精华版本，并提供带引用的 RAG 精准问答和教师多轮反馈。

## 技术栈

- 前端：Next.js 14 + TypeScript + Cytoscape.js
- 后端：FastAPI + Pydantic
- 数据：本地 JSON 状态层（Postgres JSONB 兼容仓储接口）+ ChromaDB 向量索引
- 文件解析：PyMuPDF、Markdown/TXT、python-docx

## 环境依赖

- Node.js 20+
- Python 3.11+
- 可选：Docker / Docker Compose

## 本地启动

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

cd frontend
npm install
cd ..

cp backend/.env.example backend/.env
npm run dev:backend
```

另开终端：

```bash
npm run dev:frontend
```

访问：

- 前端：http://localhost:3000
- 后端：http://localhost:8000/docs

## 使用流程

1. 在左侧上传 PDF / Markdown / TXT / DOCX 教材。
2. 点击“解析教材”，系统生成章节结构和有效正文统计。
3. 点击“构建图谱”，生成单本或多本教材知识图谱。
4. 上传并解析两本以上教材后，点击“跨教材整合”。
5. 在右侧查看 merge / keep / remove 决策和 30% 压缩比。
6. 点击“建立 RAG 索引”，在 RAG 面板提问并查看引用来源。
7. 在教师对话面板输入反馈，例如“这个知识点不应该删除，请保留”。
8. 在报告面板生成 `report/整合报告.md`。

## 配置说明

`backend/.env` 可配置：

```bash
LLM_BASE_URL=https://api.openai.com/v1
LLM_API_KEY=
LLM_MODEL=gpt-4o
RAG_TEMPERATURE=0.2
RAG_MAX_TOKENS=1200
RAG_TIMEOUT_SECONDS=45
DATABASE_URL=postgresql://postgres:postgres@localhost:5432/knowledge_agent
EMBEDDING_MODEL=BAAI/bge-large-zh-v1.5
CHROMA_DB_DIR=backend/chroma_db
EXTERNAL_CHROMA_DB_DIR=/Users/zhangjinkai/textbooks/medical-rag/chroma_db
```

RAG 检索优先使用 ChromaDB + sentence-transformers embedding。若 Chroma 或本地 embedding 失败，会自动回退到词项检索。答案生成使用 OpenAI-compatible Chat Completions 接口；无 API key 或模型调用失败时，会自动回退到本地检索摘要，保证演示不中断。

如需启用 ChromaDB 与本地 embedding 模型，可额外安装：

```bash
pip install -r backend/requirements-ai.txt
```

## Docker 启动

```bash
docker compose up
```

## 注意

不要将教材 PDF 推送到 GitHub。仓库已在 `.gitignore` 中排除：

```gitignore
data/textbooks/*.pdf
*.pdf
```
