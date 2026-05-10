# CURRENT

更新时间：2026-05-10

## 项目状态

LogosForge 是面向黑客松演示的"学科知识整合智能体"全栈原型，已完成核心链路并接入真实 LLM：

- **前端**：Next.js 14 + TypeScript，双页面架构：
  - `/` 工作台：教材上传、解析、整合、RAG 索引、教师对话、报告生成
  - `/graph` 知识图谱：全屏图谱画布、教材选择构建、搜索高亮、节点详情侧栏、关系图例、来源过滤
  - 顶部导航栏切换两个页面
- **后端**：FastAPI API 服务，覆盖教材上传解析、LLM 知识点抽取、LLM 关系推断、跨教材合并、RAG 索引与问答、教师反馈 LLM 对话、报告生成。
- **LLM 集成**：已接入 mimo-v2.5-pro 模型（OpenAI-compatible），支持：
  - LLM 知识点抽取（每章提取 8 个核心概念）
  - LLM 语义关系推断（prerequisite/contains/applies_to/parallel）
  - 教师对话 AI 回复（结构化决策修改建议）
  - 所有 LLM 调用保留正则/关键词 fallback，无 key 时自动降级
  - 适配 mimo 模型的 `reasoning_content` 字段
- **RAG**：ChromaDB + BGE-large-zh-v1.5 embedding 检索，3 层 fallback（LLM -> 词项 -> 本地摘要）。
- **数据**：已导入 7 本医学教材（5562 chunks），教材有 chapters 结构，支持按本构建图谱。
- **并行加速**：图谱构建使用 ThreadPoolExecutor 并行处理章节，6 路并发。
- **进度弹窗**：所有耗时操作（解析/建图/整合/索引/检索/对话/报告）均有步骤化进度弹窗。

## 页面结构

### 工作台 `/`
- 左侧面板：上传区、操作按钮（解析/整合/索引）、教材列表（显示已解析/已构建状态）
- 右侧面板：整合决策 / RAG 问答 / 教师对话 / 报告 四个 tab

### 知识图谱 `/graph`
- 顶部控制栏：教材选择 checkbox、LLM 开关、构建按钮
- 全屏画布：Cytoscape.js 图谱可视化，支持搜索高亮、节点点击详情、关系图例、来源过滤

## 运行入口

后端：

```bash
cd /path/to/zju_hackerthon
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

## API 端点

| 端点 | 说明 |
|------|------|
| `POST /api/textbooks/upload` | 上传教材文件 |
| `POST /api/textbooks/parse` | 解析教材（跳过已解析的） |
| `POST /api/graph/build` | 构建图谱（支持 textbook_ids 多选 + use_llm 开关） |
| `POST /api/graph/merge` | 跨教材整合 |
| `POST /api/rag/index` | 建立 RAG 索引 |
| `POST /api/rag/query` | RAG 问答 |
| `POST /api/teacher/chat` | 教师对话（LLM 驱动） |
| `POST /api/report/generate` | 生成整合报告 |

## 最近验证

- 前端生产构建通过：`npm run build`，生成 `/`（5.4kB）和 `/graph`（120kB）两个路由
- LLM 知识点抽取验证：返回高质量知识点（如"细胞基本单位"、"细胞膜选择性通透性"）
- LLM 关系推断验证：max_tokens=2000 时正常返回 JSON 关系数组
- 并行构建验证：局部解剖学 8 章从 ~64s 降到 ~12s
- 进度弹窗验证：步骤化显示 + 计时器 + 状态图标

## 当前注意事项

- `.env`、PDF、`node_modules`、`.next`、Chroma 本地库和 `state.json` 已在 `.gitignore` 中排除。
- `state.json` 约 26MB，包含 7 本教材的完整数据（chapters + chunks）。
- mimo 模型的 `reasoning_content` 会消耗大量 token，LLM 调用的 max_tokens 需 >= 2000。
- 图谱构建对大教材（248 章）仍需约 7 分钟（并行后），小教材（8 章）约 12 秒。
- 当前数据层以本地 JSON 状态模拟，生产化需迁移到 Postgres。

## 下一位 Agent 的起点

1. 先检查 `git status --short`，避免覆盖用户新改动。
2. 启动后端和前端，访问 `/` 和 `/graph` 验证两个页面。
3. 若要继续增强，参考 `docs/TODO.md` 中的待办项。
