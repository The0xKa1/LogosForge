from __future__ import annotations

import itertools
import json
import re
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed

import requests

from ..config import settings
from ..models import KnowledgeEdge, KnowledgeGraph, KnowledgeNode, MergeDecision, Textbook


KEYWORD_RE = re.compile(r"([\u4e00-\u9fa5A-Za-z][\u4e00-\u9fa5A-Za-z0-9]{1,14})(?:是|指|包括|分为|可导致|用于|依赖)")
CATEGORY_HINTS = {
    "机制": ("机制", "过程", "反应", "调节", "导致", "影响"),
    "结构": ("结构", "组织", "细胞", "器官", "系统"),
    "方法": ("方法", "技术", "诊断", "检测", "治疗"),
    "应用": ("应用", "用于", "临床", "病例"),
    "现象": ("现象", "表现", "症状", "改变"),
}


def _process_chapter(textbook: Textbook, chapter, max_nodes: int, use_llm: bool) -> tuple[list[KnowledgeNode], list[KnowledgeEdge]]:
    """处理单个章节：抽取知识点 + 推断关系（供线程池调用）"""
    if use_llm:
        chapter_nodes = _extract_nodes_with_llm(textbook, chapter.title, chapter.page_start, chapter.content, max_nodes)
        chapter_edges = _infer_edges_with_llm(chapter_nodes)
    else:
        chapter_nodes = _extract_nodes(textbook, chapter.title, chapter.page_start, chapter.content, max_nodes)
        chapter_edges = _infer_edges(chapter_nodes)
    return chapter_nodes, chapter_edges


def build_graph_for_textbook(textbook: Textbook, max_nodes_per_chapter: int = 8, max_workers: int = 6, use_llm: bool = True) -> KnowledgeGraph:
    nodes: list[KnowledgeNode] = []
    edges: list[KnowledgeEdge] = []

    # 使用线程池并行处理各章节
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {
            executor.submit(_process_chapter, textbook, chapter, max_nodes_per_chapter, use_llm): chapter
            for chapter in textbook.chapters
        }
        for future in as_completed(futures):
            chapter_nodes, chapter_edges = future.result()
            nodes.extend(chapter_nodes)
            edges.extend(chapter_edges)

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
        paragraph = f"【{node.name}】{node.definition} 该知识点属于{node.category}，建议在{node.chapter}相关教学环节讲授。"
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


def _extract_nodes_with_llm(textbook: Textbook, chapter: str, page: int, content: str, max_nodes: int) -> list[KnowledgeNode]:
    """使用 LLM 抽取知识点，失败时回退到正则版本"""
    # 如果没有配置 API key，直接使用正则版本
    if not settings.llm_api_key:
        return _extract_nodes(textbook, chapter, page, content, max_nodes)

    try:
        # 截取前 2000 字符作为上下文
        context = content[:2000]

        prompt = f"""请从以下教材章节内容中提取 {max_nodes} 个核心知识点。

章节标题：{chapter}
教材名称：{textbook.title}

内容：
{context}

请以 JSON 数组格式返回知识点，每个知识点包含：
- name: 知识点名称（简短，2-10个字）
- definition: 知识点定义或解释（50-200字）
- category: 分类（概念/方法/现象/机制/结构/应用）

要求：
1. 只提取章节中最核心的知识点
2. 定义要准确、完整
3. 不要编造内容，只基于原文提取
4. 返回纯 JSON，不要有其他文字

示例格式：
[{{"name": "知识点名称", "definition": "知识点的定义", "category": "概念"}}]"""

        response = requests.post(
            f"{settings.llm_base_url}/chat/completions",
            headers={
                "Authorization": f"Bearer {settings.llm_api_key}",
                "Content-Type": "application/json"
            },
            json={
                "model": settings.llm_model,
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.2,
                "max_tokens": 2000,
            },
            timeout=30,
        )

        if response.status_code != 200:
            return _extract_nodes(textbook, chapter, page, content, max_nodes)

        result = response.json()
        msg = result.get("choices", [{}])[0].get("message", {})
        content_text = msg.get("content", "")
        # Fallback: some models (e.g. mimo) put output in reasoning_content
        if not content_text.strip():
            content_text = msg.get("reasoning_content", "")

        # 解析 JSON
        # 尝试提取 JSON 部分（可能被包裹在 ```json ... ``` 中）
        json_match = re.search(r'\[.*\]', content_text, re.DOTALL)
        if not json_match:
            return _extract_nodes(textbook, chapter, page, content, max_nodes)

        knowledge_points = json.loads(json_match.group())

        nodes = []
        seen = set()
        for kp in knowledge_points[:max_nodes]:
            name = kp.get("name", "").strip()
            definition = kp.get("definition", "").strip()
            category = kp.get("category", "概念").strip()

            if not name or not definition or name in seen:
                continue

            seen.add(name)
            nodes.append(
                KnowledgeNode(
                    textbook_id=textbook.textbook_id,
                    name=name,
                    definition=definition,
                    category=category if category in ["概念", "方法", "现象", "机制", "结构", "应用"] else "概念",
                    chapter=chapter,
                    page=page,
                    source_textbooks=[textbook.title],
                    evidence=definition,
                )
            )

        return nodes if nodes else _extract_nodes(textbook, chapter, page, content, max_nodes)

    except Exception:
        # 任何异常都回退到正则版本
        return _extract_nodes(textbook, chapter, page, content, max_nodes)


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


def _infer_edges_with_llm(nodes: list[KnowledgeNode]) -> list[KnowledgeEdge]:
    """使用 LLM 推断语义关系，失败时回退到位置关系"""
    # 如果没有配置 API key 或节点太少，直接使用位置关系
    if not settings.llm_api_key or len(nodes) < 2:
        return _infer_edges(nodes)

    try:
        # 构建节点信息
        nodes_info = []
        for i, node in enumerate(nodes):
            nodes_info.append(f"{i+1}. {node.name}: {node.definition[:100]}")

        nodes_text = "\n".join(nodes_info)

        prompt = f"""请分析以下知识点之间的关系，返回 JSON 数组格式的关系列表。

知识点列表：
{nodes_text}

关系类型：
- prerequisite: 学习 A 前需要先理解 B（B 是 A 的前置知识）
- contains: A 包含或涵盖 B（A 是更大的概念）
- applies_to: A 应用于 B（A 是方法，B 是应用场景）
- parallel: A 和 B 是并列关系（同一层级的概念）

请返回 JSON 数组，每个关系包含：
- source: 源知识点名称
- target: 目标知识点名称
- relation_type: 关系类型（prerequisite/contains/applies_to/parallel）
- description: 关系描述（20字以内）

要求：
1. 只返回明显、确定的关系
2. 每对知识点最多一个关系
3. 返回纯 JSON，不要有其他文字

示例格式：
[{{"source": "知识点A", "target": "知识点B", "relation_type": "prerequisite", "description": "学习B前需理解A"}}]"""

        response = requests.post(
            f"{settings.llm_base_url}/chat/completions",
            headers={
                "Authorization": f"Bearer {settings.llm_api_key}",
                "Content-Type": "application/json"
            },
            json={
                "model": settings.llm_model,
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.2,
                "max_tokens": 2000,
            },
            timeout=30,
        )

        if response.status_code != 200:
            return _infer_edges(nodes)

        result = response.json()
        msg = result.get("choices", [{}])[0].get("message", {})
        content_text = msg.get("content", "")
        if not content_text.strip():
            content_text = msg.get("reasoning_content", "")

        # 解析 JSON
        json_match = re.search(r'\[.*\]', content_text, re.DOTALL)
        if not json_match:
            return _infer_edges(nodes)

        relations = json.loads(json_match.group())

        # 构建节点名称到 ID 的映射
        name_to_node = {node.name: node for node in nodes}

        edges = []
        seen_edges = set()

        for rel in relations:
            source_name = rel.get("source", "").strip()
            target_name = rel.get("target", "").strip()
            relation_type = rel.get("relation_type", "").strip()
            description = rel.get("description", "").strip()

            if not source_name or not target_name or not relation_type:
                continue

            # 验证节点存在
            source_node = name_to_node.get(source_name)
            target_node = name_to_node.get(target_name)

            if not source_node or not target_node:
                continue

            # 验证关系类型
            if relation_type not in ["prerequisite", "contains", "applies_to", "parallel"]:
                continue

            # 避免重复边
            edge_key = (source_node.id, target_node.id, relation_type)
            if edge_key in seen_edges:
                continue

            seen_edges.add(edge_key)
            edges.append(
                KnowledgeEdge(
                    source=source_node.id,
                    target=target_node.id,
                    relation_type=relation_type,
                    description=description if description else f"{source_name} 与 {target_name} 存在 {relation_type} 关系",
                )
            )

        # 如果 LLM 没有返回足够的关系，补充位置关系
        if len(edges) < len(nodes) // 2:
            position_edges = _infer_edges(nodes)
            for edge in position_edges:
                edge_key = (edge.source, edge.target, edge.relation_type)
                if edge_key not in seen_edges:
                    edges.append(edge)
                    seen_edges.add(edge_key)

        return edges if edges else _infer_edges(nodes)

    except Exception:
        # 任何异常都回退到位置关系
        return _infer_edges(nodes)


def _category_for(text: str) -> str:
    for category, hints in CATEGORY_HINTS.items():
        if any(hint in text for hint in hints):
            return category
    return "概念"


# 医学术语同义词表
MEDICAL_SYNONYMS = {
    # 英文-中文映射
    "leukocyte": "白细胞",
    "wbc": "白细胞",
    "white blood cell": "白细胞",
    "rbc": "红细胞",
    "red blood cell": "红细胞",
    "erythrocyte": "红细胞",
    "hemoglobin": "血红蛋白",
    "hb": "血红蛋白",
    "dna": "脱氧核糖核酸",
    "rna": "核糖核酸",
    "atp": "三磷酸腺苷",
    "adp": "二磷酸腺苷",
    "nad": "烟酰胺腺嘌呤二核苷酸",
    "nadp": "烟酰胺腺嘌呤二核苷酸磷酸",
    "coa": "辅酶a",
    "dna": "脱氧核糖核酸",
    "rna": "核糖核酸",
    "pcr": "聚合酶链式反应",
    "elisa": "酶联免疫吸附测定",
    "mri": "磁共振成像",
    "ct": "计算机断层扫描",
    "ecg": "心电图",
    "eeg": "脑电图",
    "iga": "免疫球蛋白a",
    "igg": "免疫球蛋白g",
    "igm": "免疫球蛋白m",
    "ige": "免疫球蛋白e",
    "igd": "免疫球蛋白d",
    # 常见中文同义词
    "血压": "动脉血压",
    "血糖": "血液葡萄糖",
    "血脂": "血液脂质",
    "心率": "心脏搏动频率",
    "呼吸频率": "呼吸次数",
    "体温": "身体温度",
    "白血球": "白细胞",
    "红血球": "红细胞",
    "血小板": "血栓细胞",
    "淋巴球": "淋巴细胞",
    "单核球": "单核细胞",
    "嗜中性球": "中性粒细胞",
    "嗜酸性球": "嗜酸性粒细胞",
    "嗜碱性球": "嗜碱性粒细胞",
    # 常见缩写展开
    "高血压": "动脉高血压",
    "糖尿病": "糖尿病 mellitus",
    "冠心病": "冠状动脉粥样硬化性心脏病",
    "心梗": "心肌梗死",
    "脑梗": "脑梗死",
    "肺结核": "结核病",
    "乙肝": "乙型肝炎",
    "丙肝": "丙型肝炎",
    "艾滋": "获得性免疫缺陷综合征",
    "aids": "获得性免疫缺陷综合征",
    "sars": "严重急性呼吸综合征",
    "covid": "新型冠状病毒肺炎",
    "新冠": "新型冠状病毒肺炎",
}


def _canonical(name: str) -> str:
    """规范化知识点名称，用于合并去重"""
    # 转小写
    lowered = name.lower().strip()

    # 应用同义词表
    for synonym, canonical in MEDICAL_SYNONYMS.items():
        if synonym in lowered:
            lowered = lowered.replace(synonym, canonical)

    # 去除常见后缀（不影响核心含义）
    suffixes_to_remove = ["症", "病", "反应", "综合征", "障碍", "异常", "改变", "过程", "机制", "原理", "理论", "学说"]
    for suffix in suffixes_to_remove:
        if lowered.endswith(suffix) and len(lowered) > len(suffix) + 1:
            lowered = lowered[:-len(suffix)]

    # 去除特殊字符和空格
    cleaned = re.sub(r"[\s_\-（）()《》\"'\\d]", "", lowered)

    # 去除重复字符
    cleaned = re.sub(r'(.)\1+', r'\1', cleaned)

    return cleaned


def _merge_definitions(nodes: list[KnowledgeNode]) -> str:
    definitions = []
    for node in nodes:
        if node.definition not in definitions:
            definitions.append(node.definition)
    return "；".join(definitions[:3])[:500]
