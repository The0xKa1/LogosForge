"""Tests for the textbook parser service."""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from backend.app.models import ParseStatus
from backend.app.services.parser import parse_textbook


@pytest.fixture
def sample_txt(tmp_path: Path) -> Path:
    """Create a sample textbook file for testing."""
    content = """第一章 细胞的基本结构

细胞是生物体的基本结构和功能单位。细胞膜是细胞与外界环境之间的界膜，
具有选择性通透性。细胞质是细胞膜以内、细胞核以外的全部物质，包括细胞
器和细胞质基质。细胞核是细胞的控制中心，含有遗传物质 DNA。

第二章 细胞的代谢

物质跨膜转运是细胞维持内环境稳定的重要机制。被动转运包括简单扩散和
协助扩散，不消耗能量。主动转运需要消耗 ATP，可以逆浓度梯度转运物质。
"""
    path = tmp_path / "sample.txt"
    path.write_text(content, encoding="utf-8")
    return path


def test_parse_textbook_txt(sample_txt: Path) -> None:
    """Parse a .txt file without raising exceptions."""
    result = parse_textbook(sample_txt, textbook_id="test_book")
    assert result.status == ParseStatus.completed
    assert result.filename == "sample.txt"
    assert len(result.chapters) >= 1
    assert result.effective_chars > 0


def test_parse_textbook_unsupported_format(tmp_path: Path) -> None:
    """Unsupported formats should return failed status."""
    path = tmp_path / "data.xyz"
    path.write_text("content", encoding="utf-8")
    result = parse_textbook(path, textbook_id="test_book")
    assert result.status == ParseStatus.failed
    assert "Unsupported format" in (result.error or "")


def test_parse_textbook_empty_file(tmp_path: Path) -> None:
    """Empty files should still parse without crashing."""
    path = tmp_path / "empty.txt"
    path.write_text("", encoding="utf-8")
    result = parse_textbook(path, textbook_id="test_book")
    assert result.status == ParseStatus.completed
    assert result.effective_chars == 0
