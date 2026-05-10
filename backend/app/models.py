from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Literal
from uuid import uuid4

from pydantic import BaseModel, Field


def new_id(prefix: str) -> str:
    return f"{prefix}_{uuid4().hex[:10]}"


class ParseStatus(str, Enum):
    uploaded = "uploaded"
    parsing = "parsing"
    completed = "completed"
    failed = "failed"


class Chapter(BaseModel):
    chapter_id: str = Field(default_factory=lambda: new_id("ch"))
    title: str
    page_start: int = 1
    page_end: int = 1
    content: str
    char_count: int


class Textbook(BaseModel):
    textbook_id: str = Field(default_factory=lambda: new_id("book"))
    filename: str
    title: str
    file_format: str
    size: int = 0
    total_pages: int = 0
    total_chars: int = 0
    effective_chars: int = 0
    status: ParseStatus = ParseStatus.uploaded
    error: str | None = None
    chapters: list[Chapter] = Field(default_factory=list)
    graph_built: bool = False
    created_at: datetime = Field(default_factory=datetime.utcnow)


class KnowledgeNode(BaseModel):
    id: str = Field(default_factory=lambda: new_id("node"))
    textbook_id: str
    name: str
    definition: str
    category: Literal["概念", "方法", "现象", "机制", "结构", "应用", "核心概念"] = "概念"
    chapter: str
    page: int = 1
    frequency: int = 1
    source_textbooks: list[str] = Field(default_factory=list)
    evidence: str = ""


class KnowledgeEdge(BaseModel):
    id: str = Field(default_factory=lambda: new_id("edge"))
    source: str
    target: str
    relation_type: Literal["prerequisite", "parallel", "contains", "applies_to"]
    description: str


class KnowledgeGraph(BaseModel):
    textbook_id: str | None = None
    nodes: list[KnowledgeNode] = Field(default_factory=list)
    edges: list[KnowledgeEdge] = Field(default_factory=list)


class MergeDecision(BaseModel):
    decision_id: str = Field(default_factory=lambda: new_id("merge"))
    action: Literal["merge", "keep", "remove"]
    affected_nodes: list[str]
    result_node: str | None = None
    reason: str
    confidence: float = 0.75
    status: Literal["active", "overridden"] = "active"


class Chunk(BaseModel):
    chunk_id: str = Field(default_factory=lambda: new_id("chunk"))
    textbook_id: str
    textbook: str
    chapter: str
    page: int
    text: str
    relevance_score: float = 0.0


class RagAnswer(BaseModel):
    answer: str
    citations: list[dict[str, Any]]
    source_chunks: list[str]


class ChatMessage(BaseModel):
    id: str = Field(default_factory=lambda: new_id("msg"))
    role: Literal["teacher", "agent"]
    content: str
    created_at: datetime = Field(default_factory=datetime.utcnow)


class ProjectState(BaseModel):
    textbooks: list[Textbook] = Field(default_factory=list)
    graph: KnowledgeGraph = Field(default_factory=KnowledgeGraph)
    graphs: dict[str, KnowledgeGraph] = Field(default_factory=dict)
    decisions: list[MergeDecision] = Field(default_factory=list)
    chunks: list[Chunk] = Field(default_factory=list)
    chat_history: list[ChatMessage] = Field(default_factory=list)
    integrated_text: str = ""
    compression_ratio: float = 0.0

