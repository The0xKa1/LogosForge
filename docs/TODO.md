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
- [ ] @next-agent 为前端增加加载中、失败重试、空状态和长任务提示，尤其是索引导入与图谱构建。
- [ ] @next-agent 优化图谱视觉编码：节点来源颜色、频次大小、关系类型样式、点击后的证据侧栏。
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

## 风险与备注

- 真实教材导入依赖本机 `/Users/zhangjinkai/textbooks/medical-rag` 的既有数据和模型缓存；换机器后需要重新准备数据。
- LLM 配置来自本地 `backend/.env`，禁止提交真实 key。
- 当前抽取、对齐和整合仍偏 demo 级，赛题答辩时应明确说明 mock fallback 和后续生产化路径。
