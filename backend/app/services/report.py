from __future__ import annotations

from pathlib import Path

from ..models import ProjectState


def render_report(state: ProjectState, project_root: Path) -> str:
    original_chars = sum(book.effective_chars for book in state.textbooks)
    integrated_chars = len(state.integrated_text)
    ratio = integrated_chars / original_chars if original_chars else 0
    merge_count = sum(1 for decision in state.decisions if decision.action == "merge")
    keep_count = sum(1 for decision in state.decisions if decision.action == "keep")
    remove_count = sum(1 for decision in state.decisions if decision.action == "remove")

    examples = state.decisions[:5]
    example_text = "\n".join(
        f"- `{item.action}`：{item.reason} 置信度 {item.confidence:.2f}" for item in examples
    ) or "- 暂无整合决策，请先构建并整合知识图谱。"

    content = f"""# 学科知识整合报告

## 整合概览

- 原始教材数量：{len(state.textbooks)}
- 原始有效正文总字数：{original_chars}
- 整合后字数：{integrated_chars}
- 压缩比：{ratio:.2%}

## 整合决策摘要

- 合并：{merge_count} 项
- 保留：{keep_count} 项
- 删除冗余：{remove_count} 项
- 决策总数：{len(state.decisions)}

## 知识图谱统计

- 整合后节点数：{len(state.graph.nodes)}
- 整合后关系数：{len(state.graph.edges)}
- RAG 知识块数量：{len(state.chunks)}

## 重点整合案例

{example_text}

## 教学完整性说明

系统按“基础概念 -> 前置依赖 -> 核心机制 -> 对比关系 -> 应用场景”的顺序组织整合稿。
合并节点时保留原始证据和 prerequisite 关系，避免删除重复内容后造成教学链路断裂。
若某教材缺少整合大纲中的关键节点，系统会在跨教材对齐中标记为缺失，并建议教师在多轮对话中确认是否补充。

## 30% 压缩约束

本报告使用有效正文作为压缩比分母，过滤封面、版权、目录、前言、作者简介、参考文献、索引等非教学正文。
当前整合稿压缩比为 {ratio:.2%}，{"满足" if ratio <= 0.3 else "未满足"} 不超过 30% 的要求。
"""
    report_path = project_root / "report" / "整合报告.md"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(content, encoding="utf-8")
    return content

