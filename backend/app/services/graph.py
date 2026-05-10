from __future__ import annotations

import itertools
import re
from collections import defaultdict

from ..models import KnowledgeEdge, KnowledgeGraph, KnowledgeNode, MergeDecision, Textbook


KEYWORD_RE = re.compile(r"([\u4e00-\u9fa5A-Za-z][\u4e00-\u9fa5A-Za-z0-9]{1,14})(?:是|指|包括|分为|可导致|用于|依赖)")
CATEGORY_HINTS = {
    "机制": ("机制", "过程", "反应", "调节", "导致", "影响"),
    "结构": ("结构", "组织", "细胞", "器官", "系统"),
    "方法": ("方法", "技术", "诊断", "检测", "治疗"),
    "应用": ("应用", "用于", "临床", "病例"),
    "现象": ("现象", "表现", "症状", "改变"),
}


def build_graph_for_textbook(textbook: Textbook, max_nodes_per_chapter: int = 5) -> KnowledgeGraph:
    nodes: list[KnowledgeNode] = []
    edges: list[KnowledgeEdge] = []

    for chapter in textbook.chapters:
        chapter_nodes = _extract_nodes(textbook, chapter.title, chapter.page_start, chapter.content, max_nodes_per_chapter)
        nodes.extend(chapter_nodes)
        edges.extend(_infer_edges(chapter_nodes))

    return KnowledgeGraph(textbook_id=textbook.textbook_id, nodes=nodes, edges=edges)


def merge_graphs(graphs: list[KnowledgeGraph]) -> tuple[KnowledgeGraph, list[MergeDecision]]:
    all_nodes = list(itertools.chain.from_iterable(graph.nodes for graph in graphs))
    all_edges = list(itertools.chain.from_iterable(graph.edges for graph in graphs))
    groups: dict[str, list[KnowledgeNode]] = defaultdict(list)

    for node in all_nodes:
        groups[_canonical(node.name)].append(node)

    merged_nodes: list[KnowledgeNode] = []
    decisions: list[MergeDecision] = []
    replaced: dict[str, str] = {}

    for _, group in groups.items():
        if len(group) == 1:
            node = group[0]
            merged_nodes.append(node)
            decisions.append(
                MergeDecision(
                    action="keep",
                    affected_nodes=[node.id],
                    result_node=node.id,
                    reason=f"'{node.name}' 只在当前教材集合中形成一个独立知识点，保留用于保证知识覆盖。",
                    confidence=0.78,
                )
            )
            continue

        best = max(group, key=lambda n: len(n.definition) + len(n.evidence))
        merged = best.model_copy(deep=True)
        merged.id = f"merged_{_canonical(best.name)[:12]}"
        merged.frequency = len(group)
        merged.source_textbooks = sorted({src for node in group for src in (node.source_textbooks or [node.textbook_id])})
        merged.definition = _merge_definitions(group)
        merged.evidence = "\n".join(node.evidence for node in group[:3])
        merged_nodes.append(merged)
        for node in group:
            replaced[node.id] = merged.id
        decisions.append(
            MergeDecision(
                action="merge",
                affected_nodes=[node.id for node in group],
                result_node=merged.id,
                reason=f"{len(group)} 本教材都覆盖 '{best.name}'，系统合并重复定义，并保留信息最完整的表述作为主定义。",
                confidence=min(0.95, 0.72 + 0.05 * len(group)),
            )
        )

    merged_edges = []
    seen_edges = set()
    for edge in all_edges:
        source = replaced.get(edge.source, edge.source)
        target = replaced.get(edge.target, edge.target)
        key = (source, target, edge.relation_type)
        if source == target or key in seen_edges:
            continue
        seen_edges.add(key)
        merged_edges.append(edge.model_copy(update={"source": source, "target": target}))

    for node in all_nodes:
        if node.id in replaced and node.id != replaced[node.id]:
            decisions.append(
                MergeDecision(
                    action="remove",
                    affected_nodes=[node.id],
                    result_node=replaced[node.id],
                    reason=f"'{node.name}' 已被合并进整合节点，删除冗余节点但保留原文证据。",
                    confidence=0.82,
                )
            )

    return KnowledgeGraph(nodes=merged_nodes, edges=merged_edges), decisions


def build_integrated_text(graph: KnowledgeGraph, original_chars: int, target_ratio: float = 0.3) -> tuple[str, float]:
    budget = max(1, int(original_chars * target_ratio))
    ordered = sorted(graph.nodes, key=lambda n: (-n.frequency, n.chapter, n.name))
    sections = []
    used = 0
    for node in ordered:
        paragraph = f"【{node.name}】{node.definition} 该知识点属于{node.category}，建议在“{node.chapter}”相关教学环节讲授。"
        if used + len(paragraph) > budget:
            continue
        sections.append(paragraph)
        used += len(paragraph)
    if not sections and ordered:
        node = ordered[0]
        fallback = f"【{node.name}】{node.definition}"
        sections.append(fallback[:budget])
        used = len(sections[0])
    text = "\n\n".join(sections)
    ratio = used / original_chars if original_chars else 0
    return text, ratio


def _extract_nodes(textbook: Textbook, chapter: str, page: int, content: str, max_nodes: int) -> list[KnowledgeNode]:
    sentences = [s.strip() for s in re.split(r"[。！？\n]", content) if len(s.strip()) > 18]
    candidates: list[tuple[str, str]] = []
    for sentence in sentences:
        match = KEYWORD_RE.search(sentence)
        if match:
            candidates.append((match.group(1), sentence[:180]))
        elif len(candidates) < 2:
            phrase = sentence[: min(8, len(sentence))]
            candidates.append((phrase, sentence[:180]))
        if len(candidates) >= max_nodes:
            break

    nodes = []
    seen = set()
    for name, definition in candidates:
        clean_name = re.sub(r"[^\u4e00-\u9fa5A-Za-z0-9]", "", name)[:18]
        if not clean_name or clean_name in seen:
            continue
        seen.add(clean_name)
        nodes.append(
            KnowledgeNode(
                textbook_id=textbook.textbook_id,
                name=clean_name,
                definition=definition,
                category=_category_for(definition),
                chapter=chapter,
                page=page,
                source_textbooks=[textbook.title],
                evidence=definition,
            )
        )
    return nodes


def _infer_edges(nodes: list[KnowledgeNode]) -> list[KnowledgeEdge]:
    edges: list[KnowledgeEdge] = []
    for index, node in enumerate(nodes):
        if index > 0:
            prev = nodes[index - 1]
            edges.append(
                KnowledgeEdge(
                    source=prev.id,
                    target=node.id,
                    relation_type="prerequisite",
                    description=f"学习 {node.name} 前通常需要理解 {prev.name}。",
                )
            )
        if index > 1:
            peer = nodes[index - 2]
            edges.append(
                KnowledgeEdge(
                    source=peer.id,
                    target=node.id,
                    relation_type="parallel",
                    description=f"{peer.name} 与 {node.name} 位于同一章节知识层级。",
                )
            )
    if len(nodes) >= 3:
        edges.append(
            KnowledgeEdge(
                source=nodes[0].id,
                target=nodes[-1].id,
                relation_type="contains",
                description=f"{nodes[0].name} 可作为章节上位概念组织 {nodes[-1].name}。",
            )
        )
    return edges


def _category_for(text: str) -> str:
    for category, hints in CATEGORY_HINTS.items():
        if any(hint in text for hint in hints):
            return category
    return "概念"


def _canonical(name: str) -> str:
    lowered = name.lower().replace("leukocyte", "白细胞")
    return re.sub(r"[\s_\-（）()《》“”\"']", "", lowered)


def _merge_definitions(nodes: list[KnowledgeNode]) -> str:
    definitions = []
    for node in nodes:
        if node.definition not in definitions:
            definitions.append(node.definition)
    return "；".join(definitions[:3])[:500]
