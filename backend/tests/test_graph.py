"""Tests for graph building and merging logic."""

from __future__ import annotations

import pytest

from backend.app.models import KnowledgeEdge, KnowledgeGraph, KnowledgeNode
from backend.app.services.graph import merge_graphs


def _make_node(name: str, textbook_id: str = "book_1", definition: str = "") -> KnowledgeNode:
    """Helper to create a test node."""
    return KnowledgeNode(
        textbook_id=textbook_id,
        name=name,
        definition=definition or f"{name}的定义",
        category="概念",
        chapter="第一章",
        page=1,
        source_textbooks=[textbook_id],
    )


def test_merge_graphs_empty_list() -> None:
    """Merging zero graphs should return empty graph and no decisions."""
    graph, decisions = merge_graphs([])
    assert len(graph.nodes) == 0
    assert len(graph.edges) == 0
    assert len(decisions) == 0


def test_merge_graphs_single_graph() -> None:
    """A single graph should pass through with keep decisions."""
    node = _make_node("炎症")
    graph = KnowledgeGraph(textbook_id="book_1", nodes=[node], edges=[])
    merged, decisions = merge_graphs([graph])
    assert len(merged.nodes) == 1
    assert merged.nodes[0].name == "炎症"
    assert all(d.action == "keep" for d in decisions)


def test_merge_graphs_same_name_nodes() -> None:
    """Nodes with the same canonical name across textbooks should merge."""
    node_a = _make_node("T细胞", "book_1", "T细胞在免疫应答中的分化与功能")
    node_b = _make_node("T细胞", "book_2", "T细胞介导的抗感染免疫")
    graph_a = KnowledgeGraph(textbook_id="book_1", nodes=[node_a], edges=[])
    graph_b = KnowledgeGraph(textbook_id="book_2", nodes=[node_b], edges=[])
    merged, decisions = merge_graphs([graph_a, graph_b])
    assert len(merged.nodes) == 1
    assert merged.nodes[0].frequency == 2
    merge_decisions = [d for d in decisions if d.action == "merge"]
    assert len(merge_decisions) == 1


def test_merge_graphs_different_nodes() -> None:
    """Different nodes should all be kept."""
    node_a = _make_node("炎症", "book_1")
    node_b = _make_node("细胞凋亡", "book_2")
    graph_a = KnowledgeGraph(textbook_id="book_1", nodes=[node_a], edges=[])
    graph_b = KnowledgeGraph(textbook_id="book_2", nodes=[node_b], edges=[])
    merged, decisions = merge_graphs([graph_a, graph_b])
    assert len(merged.nodes) == 2
    assert all(d.action == "keep" for d in decisions)


def test_merge_graphs_edge_remap() -> None:
    """Edges should be remapped when their source/target nodes are merged."""
    node_a1 = _make_node("炎症", "book_1", "定义A")
    node_a2 = _make_node("炎症", "book_2", "定义B")
    node_c = _make_node("渗出", "book_1")
    edge = KnowledgeEdge(source=node_a1.id, target=node_c.id, relation_type="contains", description="test")
    graph_a = KnowledgeGraph(textbook_id="book_1", nodes=[node_a1, node_c], edges=[edge])
    graph_b = KnowledgeGraph(textbook_id="book_2", nodes=[node_a2], edges=[])
    merged, _ = merge_graphs([graph_a, graph_b])
    assert len(merged.edges) == 1
    # The edge source should now point to the merged node
    assert merged.edges[0].source != node_a1.id  # remapped
