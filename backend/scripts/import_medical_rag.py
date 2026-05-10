from __future__ import annotations

import re
import sqlite3
from collections import defaultdict
from pathlib import Path

from backend.app.config import settings
from backend.app.models import Chunk, ParseStatus, Textbook, new_id
from backend.app.services.rag import index_chunks
from backend.app.storage import store


SOURCE_DB = Path("/Users/zhangjinkai/textbooks/medical-rag/chroma_db/chroma.sqlite3")


def main() -> None:
    chunks = load_chunks(SOURCE_DB)
    if not chunks:
        raise SystemExit("No chunks found in medical-rag Chroma sqlite")

    state = store.load()
    state.chunks = chunks
    state.textbooks = build_textbooks(chunks)
    store.save(state)

    print(f"Loaded {len(chunks)} chunks from {SOURCE_DB}")
    print(f"Detected {len(state.textbooks)} textbooks")
    print(f"Embedding model: {settings.embedding_model}")
    print(f"Target Chroma dir: {settings.chroma_db_dir}")
    print(index_chunks(chunks, show_progress=True))
    store.save(state)


def load_chunks(db_path: Path) -> list[Chunk]:
    rows_by_id: dict[int, dict[str, object]] = defaultdict(dict)
    with sqlite3.connect(db_path) as conn:
        cursor = conn.execute(
            """
            select id, key, string_value, int_value, float_value
            from embedding_metadata
            where key in ('chroma:document', 'source', 'chapter', 'chunk_index')
            order by id
            """
        )
        for row_id, key, string_value, int_value, float_value in cursor.fetchall():
            rows_by_id[row_id][key] = string_value if string_value is not None else int_value or float_value

    chunks: list[Chunk] = []
    for row_id, metadata in rows_by_id.items():
        text = str(metadata.get("chroma:document") or "").strip()
        source = str(metadata.get("source") or "未知教材")
        chapter = str(metadata.get("chapter") or "未知章节")
        chunk_index = int(metadata.get("chunk_index") or row_id)
        if not text:
            continue
        clean_text = _clean_document_prefix(text)
        chunks.append(
            Chunk(
                chunk_id=f"medical_{row_id}",
                textbook_id=_textbook_id(source),
                textbook=source.removesuffix(".pdf"),
                chapter=chapter,
                page=_infer_page(text, chunk_index),
                text=clean_text,
            )
        )
    return chunks


def build_textbooks(chunks: list[Chunk]) -> list[Textbook]:
    grouped: dict[str, list[Chunk]] = defaultdict(list)
    for chunk in chunks:
        grouped[chunk.textbook].append(chunk)

    textbooks = []
    for title, items in sorted(grouped.items()):
        source_name = f"{title}.pdf" if not title.endswith(".pdf") else title
        textbooks.append(
            Textbook(
                textbook_id=_textbook_id(source_name),
                filename=source_name,
                title=title.removesuffix(".pdf"),
                file_format="pdf",
                size=0,
                total_pages=max((chunk.page for chunk in items), default=0),
                total_chars=sum(len(chunk.text) for chunk in items),
                effective_chars=sum(len(re.sub(r"\s+", "", chunk.text)) for chunk in items),
                status=ParseStatus.completed,
                chapters=[],
            )
        )
    return textbooks


def _textbook_id(source: str) -> str:
    slug = re.sub(r"[^A-Za-z0-9\u4e00-\u9fa5]+", "_", source.removesuffix(".pdf")).strip("_")
    return f"medical_{slug}"[:64] or new_id("medical")


def _clean_document_prefix(text: str) -> str:
    return re.sub(r"^【[^】]+】\s*", "", text).strip()


def _infer_page(text: str, fallback: int) -> int:
    clean = _clean_document_prefix(text)
    match = re.match(r"^\s*(\d{1,4})\s*(?:\n|$)", clean)
    if match:
        return int(match.group(1))
    return max(1, fallback + 1)


if __name__ == "__main__":
    main()
