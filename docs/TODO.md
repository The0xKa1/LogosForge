# TODO

更新时间：2026-05-10

## 进行中

（无）

## 待办

- [ ] 将数据层从本地 JSON 状态仓储迁移到真实 Postgres JSONB repository，并保留当前 mock/local fallback。
- [ ] 增加 RAG benchmark 小脚本，覆盖医学教材常见问答、引用命中率和无答案拒答。
- [ ] 增加后端最小测试集，覆盖上传解析、图谱构建、RAG fallback、教师反馈更新和报告生成。
- [ ] 为 `report/整合报告.md` 接入真实运行统计，避免报告只停留在静态样例。
- [ ] 检查 Docker Compose 端到端启动，补齐 Chroma/Postgres 环境变量与持久化卷说明。
- [ ] 图谱页面增加节点关系路径高亮（选中节点时高亮关联路径）。
- [ ] 前端状态管理拆分：page.tsx 仍较复杂，可拆分为 hooks/useProjectState.ts + 子组件。
- [ ] 等 Vercel 部署最新 commit 后，访问 `https://logosforge.the0xka1.cc/api/health`、`/api/state` 和页面工作台，确认同源 API rewrite 生效。

## 已完成

- [x] 修复数据流断裂：import_medical_rag.py 从 chunk 重建 chapters，7 本教材恢复正常。
- [x] 修复 config.py 硬编码路径和 Embedding 设备硬编码（mps/cuda/cpu 自动检测）。
- [x] 接入 LLM 知识点抽取（_extract_nodes_with_llm），每章提取 8 个核心概念，保留正则 fallback。
- [x] 接入 LLM 语义关系推断（_infer_edges_with_llm），支持 prerequisite/contains/applies_to/parallel 四种关系。
- [x] 接入教师对话 LLM（_teacher_llm_reply），结构化决策修改建议，保留关键词 fallback。
- [x] 改进 _canonical 医学术语同义词表（50+ 条目）和去重逻辑。
- [x] 适配 mimo-v2.5-pro 模型 reasoning_content 字段，所有 LLM 调用 max_tokens 提升到 2000。
- [x] 图谱构建并行加速：ThreadPoolExecutor 6 路并发，8 章教材从 ~64s 降到 ~12s。
- [x] 构建图谱支持选定教材（textbook_ids 多选）+ use_llm 开关（正则/LLM 模式切换）。
- [x] 教材卡片显示 graph_built 状态（已构建/未构建），ProjectState 存储单本图谱（graphs dict）。
- [x] 进度弹窗组件（ProgressModal）：步骤化显示 + 计时器 + 状态图标 + 错误高亮。
- [x] 知识图谱页面拆分到独立路由 `/graph`，与工作台 `/` 分开，顶部导航栏切换。
- [x] 图谱交互增强：关系类型图例、来源过滤器、节点详情侧栏、搜索高亮。
- [x] 前端类型修复：Textbook 添加 graph_built，buildGraph 支持参数。
- [x] 解析端点跳过已有 chapters 的教材，不再覆盖导入脚本的状态。
- [x] 前端生产构建通过，生成 `/`（5.4kB）和 `/graph`（120kB）两个路由。
- [x] 生产前端 API 改为同源 `/api/*`，Next rewrite 到阿里云 80 端口，绕开公网 `8000` 和 mixed content 问题。

## 风险与备注

- 真实教材导入依赖外部 medical-rag Chroma sqlite 和模型缓存；换机器后需要通过 `MEDICAL_RAG_CHROMA_DB` 重新指定数据路径。
- LLM 配置来自本地 `backend/.env`，禁止提交真实 key。
- mimo 模型 reasoning_content 消耗大量 token，max_tokens 需 >= 2000 才能保证 content 非空。
- state.json 约 26MB，包含完整教材数据，git 已排除。
- `/api/state` 会返回约 26MB JSON，生产首页初始化会偏重，后续建议拆成摘要接口 + 按需详情接口。
- 若当前机器上还有其他用户手动启动的后端或前端进程，收尾时应先确认端口占用再停止。
