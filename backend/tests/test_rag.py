"""Tests for RAG chunking and retrieval."""

from __future__ import annotations

import pytest

from backend.app.models import Chapter, Textbook
from backend.app.services.rag import build_chunks


def _make_textbook(chapters: list[tuple[str, str]]) -> Textbook:
    """Helper to create a test textbook with chapters."""
    return Textbook(
        textbook_id="test_book",
        filename="test.txt",
        title="测试教材",
        file_format="txt",
        chapters=[
            Chapter(
                title=title,
                content=content,
                char_count=len(content),
                page_start=1,
            )
            for title, content in chapters
        ],
    )


def test_build_chunks_basic() -> None:
    """Chunks should be created from textbook chapters."""
    book = _make_textbook([
        ("第一章", "细胞是生物体的基本结构和功能单位。" * 50),
        ("第二章", "物质跨膜转运是细胞维持内环境稳定的重要机制。" * 50),
    ])
    chunks = build_chunks([book], chunk_size=700, overlap=80)
    assert len(chunks) > 0
    assert all(len(c.text) > 80 for c in chunks)


def test_build_chunks_respects_size() -> None:
    """Chunk text length should not exceed chunk_size."""
    book = _make_textbook([("第一章", "A" * 2000)])
    chunks = build_chunks([book], chunk_size=500, overlap=50)
    for chunk in chunks:
        assert len(chunk.text) <= 500


def test_build_chunks_metadata() -> None:
    """Chunks should carry correct textbook and chapter metadata."""
    book = _make_textbook([("绪论", "这是一段测试内容，需要足够长才能被分块处理。" * 20)])
    chunks = build_chunks([book])
    for chunk in chunks:
        assert chunk.textbook == "测试教材"
        assert chunk.chapter == "绪论"
        assert chunk.textbook_id == "test_book"


def test_build_chunks_empty_textbook() -> None:
    """Empty textbook should produce no chunks."""
    book = _make_textbook([])
    chunks = build_chunks([book])
    assert len(chunks) == 0


def test_build_chunks_overlap() -> None:
    """Overlapping chunks should share some text."""
    long_text = "。".join([f"这是第{i}个句子" for i in range(200)])
    book = _make_textbook([("第一章", long_text)])
    chunks = build_chunks([book], chunk_size=200, overlap=50)
    if len(chunks) >= 2:
        # Check that consecutive chunks share some characters
        shared = set(chunks[0].text) & set(chunks[1].text)
        assert len(shared) > 0
