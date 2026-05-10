# CURRENT

更新时间：2026-05-10

## 项目状态

LogosForge 当前是一个面向黑客松演示的“学科知识整合智能体”全栈原型，已完成可运行骨架和核心链路：

- 前端：Next.js + TypeScript 单页工作台，包含教材上传、索引状态、知识图谱画布、整合决策、RAG 问答、教师对话和报告预览入口；界面已做一轮高级感优化，当前采用 LogosForge 品牌顶栏、低饱和学术工具色系、玻璃质感三栏工作台、空状态、进度提示和按钮交互反馈。
- 后端：FastAPI API 服务，覆盖教材上传解析、知识图谱构建、跨教材合并、RAG 索引与问答、教师反馈更新、报告生成。
- RAG：已接入 OpenAI-compatible LLM 配置，优先使用 ChromaDB + BGE embedding 检索，失败时回退到词项检索和本地摘要。
- 旧项目复用：`backend/scripts/import_medical_rag.py` 可从既有 medical-rag Chroma sqlite 导入 7 本医学教材 chunk，并重建本项目 Chroma 索引。
- 文档：需求分析、系统设计、Agent 架构说明、接口文档、README、演示报告草稿已存在。

## 当前实现重点

- 知识点粒度：按“可独立讲授、考核或连接前后知识的最小教学单元”定义，类型覆盖概念、方法、现象、机制、结构、应用。
- 重复判定：名称/别名相似、定义等价、教学用途一致时合并；边界不清时保留为待教师确认。
- 教学连贯性：整合顺序按基础概念、前置依赖、核心机制、对比关系、应用场景组织，并保留 prerequisite 等关系。
- 30% 压缩比：以有效正文字符数为分母，整合精华正文字符数为分子，目标 `integrated <= original * 0.30`。

## 运行入口

后端：

```bash
uvicorn backend.app.main:app --host 127.0.0.1 --port 8000
```

前端：

```bash
cd frontend
npm run dev
```

导入既有 medical-rag 索引数据：

```bash
python3 -m backend.scripts.import_medical_rag
```

导入脚本已带进度条。运行时会读取旧 Chroma sqlite 中的 chunk，写入本项目状态，并用当前 embedding 模型重建本项目 Chroma collection。

## 最近验证

- 后端 Python 编译检查通过：`python3 -m compileall backend/app`
- 前端类型检查通过：`npm run typecheck`
- 前端生产构建通过：`npm run build`
- 浏览器预览通过：Next dev 自动落到 `http://localhost:3001`，页面标题为 LogosForge，布局在 1440px 桌面视口下为三栏工作台。
- LLM 连通性已验证，配置来自 `backend/.env`
- Chroma + BGE embedding 小样本索引和查询已验证

## 当前注意事项

- `.env`、PDF、`node_modules`、`.next`、Chroma 本地库和运行状态文件已在 `.gitignore` 中排除。
- Playwright 临时快照与本轮预览截图已在 `.gitignore` 中排除。
- `docs/第一届AI全栈黑客松赛题.pdf` 会因 `*.pdf` 规则被忽略，不会进入 GitHub。
- 完整导入 7 本教材需要本地 embedding，可能耗时数分钟。
- Chroma 旧版本可能打印 telemetry warning；当前代码已关闭匿名遥测，该 warning 不影响检索和索引。
- 当前数据层以本地 JSON 状态模拟 Postgres JSONB 结构，若进入生产化需要补真实 Postgres repository。
- 后端 CORS 已允许 `localhost/127.0.0.1` 的 `3000`、`3001`、`3002`，方便 Next 端口占用时继续联调；修改后需要重启正在运行的后端进程才会生效。

## 下一位 Agent 的起点

1. 先检查 `git status --short`，避免覆盖用户新改动。
2. 如需演示真实 7 本教材，先运行 `python3 -m backend.scripts.import_medical_rag`。
3. 启动后端和前端，再通过 `/api/rag/status` 与前端顶部状态确认 chunk 数。
4. 若要继续增强，优先处理 `docs/TODO.md` 中 P0/P1 项；前端下一步更适合做真实数据态下的图谱细节和长任务体验，而不是继续换皮。
