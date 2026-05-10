# TODO

更新时间：2026-05-10

## 进行中

- [ ] @next-agent 完整运行 `python3 -m backend.scripts.import_medical_rag`，确认 7 本医学教材 chunk 被导入并完成 Chroma 重建。
- [ ] @next-agent 用真实导入后的数据启动前后端，做一次端到端演示检查：RAG 提问、引用展示、图谱搜索、教师反馈、报告生成。

## 待办

- [ ] @next-agent 将数据层从本地 JSON 状态仓储补到真实 Postgres JSONB repository，并保留当前 mock/local fallback。
- [ ] @next-agent 增强知识点抽取：从启发式规则升级到 LLM JSON schema 抽取，并增加 schema 校验和失败回退。
- [ ] @next-agent 增强跨教材对齐：使用 embedding 候选召回 + LLM 二次判定，输出重复、互补、缺失的可解释证据。
- [ ] @next-agent 给整合结果增加“压缩前后对比”视图，展示原始字符数、精华字符数、压缩比和保留理由。
- [ ] @next-agent 增加 RAG benchmark 小脚本，覆盖医学教材常见问答、引用命中率和无答案拒答。
- [ ] @next-agent 增加后端最小测试集，覆盖上传解析、图谱构建、RAG fallback、教师反馈更新和报告生成。
- [ ] @next-agent 为前端增加更完整的长任务体验：索引导入进度、图谱构建进度、失败重试和操作日志。
- [ ] @next-agent 在真实导入数据下继续优化图谱交互：关系类型图例、来源过滤、节点证据侧栏、关系路径高亮。
- [ ] @next-agent 为 `report/整合报告.md` 接入真实运行统计，避免报告只停留在静态样例。
- [ ] @next-agent 检查 Docker Compose 端到端启动，补齐 Chroma/Postgres 环境变量与持久化卷说明。

## 已完成

- [x] @codex 搭建 Next.js + TypeScript 前端工作台。
- [x] @codex 搭建 FastAPI 后端和必需 API。
- [x] @codex 实现 PDF / MD / TXT / DOCX 解析入口。
- [x] @codex 实现启发式知识图谱构建和跨教材 merge / keep / remove 决策。
- [x] @codex 接入 OpenAI-compatible LLM 问答，并保留无 key / 调用失败 fallback。
- [x] @codex 接入 ChromaDB + BGE embedding 检索，并保留词项检索 fallback。
- [x] @codex 增加 medical-rag 导入脚本和索引进度条。
- [x] @codex 补齐需求分析、系统设计、Agent 架构说明、接口文档、README 和报告草稿。
- [x] @codex 优化前端视觉系统：LogosForge 品牌顶栏、低饱和色板、三栏工作台质感、空状态、进度提示、按钮反馈和图谱配色。
- [x] @codex 扩展后端 CORS，支持 Next dev 自动切到 `3001/3002` 时继续本地联调。

## 风险与备注

- 真实教材导入依赖本机 `/Users/zhangjinkai/textbooks/medical-rag` 的既有数据和模型缓存；换机器后需要重新准备数据。
- LLM 配置来自本地 `backend/.env`，禁止提交真实 key。
- 当前抽取、对齐和整合仍偏 demo 级，赛题答辩时应明确说明 mock fallback 和后续生产化路径。
- 若当前机器上还有其他用户手动启动的后端或前端进程，收尾时应先确认端口占用再停止，避免误杀非本项目服务。
