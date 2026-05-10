from __future__ import annotations

import re
from pathlib import Path

from fastapi import UploadFile

from ..models import Chapter, ParseStatus, Textbook


NON_CONTENT_PATTERNS = re.compile(
    r"(版权|编委|主编简介|副主编简介|前言|序言|目录|参考文献|索引|致谢|出版|封面|修订说明)"
)
CHAPTER_RE = re.compile(r"^(第[一二三四五六七八九十百千零\d]+[章节篇]\s*[^\n]{0,40}|绪论|总论)\s*$", re.MULTILINE)


async def save_upload(file: UploadFile, upload_dir: Path) -> Path:
    upload_dir.mkdir(parents=True, exist_ok=True)
    safe_name = Path(file.filename or "textbook.txt").name
    dest = upload_dir / safe_name
    with dest.open("wb") as out:
        while chunk := await file.read(1024 * 1024):
            out.write(chunk)
    return dest


def parse_textbook(path: Path, textbook_id: str | None = None) -> Textbook:
    suffix = path.suffix.lower().lstrip(".")
    parser = {
        "pdf": _parse_pdf,
        "md": _parse_plain,
        "markdown": _parse_plain,
        "txt": _parse_plain,
        "docx": _parse_docx,
    }.get(suffix)
    if parser is None:
        return Textbook(
            textbook_id=textbook_id or "",
            filename=path.name,
            title=path.stem,
            file_format=suffix,
            size=path.stat().st_size,
            status=ParseStatus.failed,
            error=f"Unsupported format: {suffix}",
        )

    try:
        chapters, pages = parser(path)
        total_chars = sum(ch.char_count for ch in chapters)
        effective_chars = sum(_effective_char_count(ch.content) for ch in chapters)
        return Textbook(
            textbook_id=textbook_id or "",
            filename=path.name,
            title=path.stem,
            file_format=suffix,
            size=path.stat().st_size,
            total_pages=pages,
            total_chars=total_chars,
            effective_chars=effective_chars,
            status=ParseStatus.completed,
            chapters=chapters,
        )
    except Exception as exc:  # pragma: no cover - defensive API error surface
        return Textbook(
            textbook_id=textbook_id or "",
            filename=path.name,
            title=path.stem,
            file_format=suffix,
            size=path.stat().st_size,
            status=ParseStatus.failed,
            error=str(exc),
        )


def _parse_pdf(path: Path) -> tuple[list[Chapter], int]:
    try:
        import fitz
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError("PyMuPDF is required to parse PDF files") from exc

    doc = fitz.open(path)
    page_texts: list[tuple[int, str]] = []
    for index, page in enumerate(doc, start=1):
        text = _strip_headers_footers(page.get_text("text"))
        if text.strip():
            page_texts.append((index, text))
    pages = len(doc)
    doc.close()
    return _split_into_chapters(page_texts, fallback_title=path.stem), pages


def _parse_plain(path: Path) -> tuple[list[Chapter], int]:
    text = path.read_text(encoding="utf-8", errors="ignore")
    return _split_into_chapters([(1, text)], fallback_title=path.stem), 1


def _parse_docx(path: Path) -> tuple[list[Chapter], int]:
    try:
        from docx import Document
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError("python-docx is required to parse docx files") from exc

    doc = Document(path)
    text = "\n".join(p.text for p in doc.paragraphs if p.text.strip())
    return _split_into_chapters([(1, text)], fallback_title=path.stem), 1


def _split_into_chapters(page_texts: list[tuple[int, str]], fallback_title: str) -> list[Chapter]:
    full = "\n".join(f"\n[[PAGE:{page}]]\n{text}" for page, text in page_texts)
    matches = list(CHAPTER_RE.finditer(full))
    chapters: list[Chapter] = []

    if not matches:
        cleaned = re.sub(r"\[\[PAGE:\d+\]\]", "", _remove_non_content(full)).strip()
        return [
            Chapter(
                title=fallback_title,
                page_start=page_texts[0][0] if page_texts else 1,
                page_end=page_texts[-1][0] if page_texts else 1,
                content=cleaned,
                char_count=len(cleaned),
            )
        ]

    for index, match in enumerate(matches):
        start = match.start()
        end = matches[index + 1].start() if index + 1 < len(matches) else len(full)
        block = full[start:end].strip()
        title = match.group(1).strip()
        cleaned = _remove_non_content(block)
        if len(cleaned) < 120:
            continue
        pages = [int(p) for p in re.findall(r"\[\[PAGE:(\d+)\]\]", block)]
        chapters.append(
            Chapter(
                title=title,
                page_start=min(pages) if pages else 1,
                page_end=max(pages) if pages else 1,
                content=re.sub(r"\[\[PAGE:\d+\]\]", "", cleaned).strip(),
                char_count=len(cleaned),
            )
        )

    if chapters:
        return chapters
    cleaned = re.sub(r"\[\[PAGE:\d+\]\]", "", _remove_non_content(full)).strip()
    return [Chapter(title=fallback_title, content=cleaned, char_count=len(cleaned))]


def _strip_headers_footers(text: str) -> str:
    lines = [line.strip() for line in text.splitlines()]
    kept = []
    for line in lines:
        if not line or re.fullmatch(r"\d+|第\s*\d+\s*页|Page\s+\d+", line, flags=re.I):
            continue
        kept.append(line)
    return "\n".join(kept)


def _remove_non_content(text: str) -> str:
    blocks = []
    for para in re.split(r"\n{2,}", text):
        if NON_CONTENT_PATTERNS.search(para[:80]):
            continue
        blocks.append(para)
    return "\n\n".join(blocks).strip()


def _effective_char_count(text: str) -> int:
    cleaned = _remove_non_content(text)
    return len(re.sub(r"\s+", "", cleaned))
