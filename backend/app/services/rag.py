from __future__ import annotations

import math
import re
import logging
from collections import Counter
from functools import lru_cache
from typing import Any

from ..config import settings
from ..models import Chunk, RagAnswer, Textbook


logger = logging.getLogger(__name__)
COLLECTION_NAME = "textbook_chunks"


def build_chunks(textbooks: list[Textbook], chunk_size: int = 700, overlap: int = 80) -> list[Chunk]:
    """将教材章节切分为固定大小的语义块，用于 RAG 索引。

    使用滑动窗口分块，每个 chunk 携带教材名、章节、页码等元数据。

    Args:
        textbooks: 已解析的教材列表。
        chunk_size: 每块最大字符数。
        overlap: 相邻块的重叠字符数。

    Returns:
        Chunk 对象列表，每个 chunk 的 text 长度 <= chunk_size。
    """
    chunks: list[Chunk] = []
    for book in textbooks:
        for chapter in book.chapters:
            text = re.sub(r"\s+", " ", chapter.content).strip()
            start = 0
            while start < len(text):
                piece = text[start : start + chunk_size]
                if len(piece) > 80:
                    chunks.append(
                        Chunk(
                            textbook_id=book.textbook_id,
                            textbook=book.title,
                            chapter=chapter.title,
                            page=chapter.page_start,
                            text=piece,
                        )
                    )
                if start + chunk_size >= len(text):
                    break
                start += chunk_size - overlap
    return chunks


def index_chunks(chunks: list[Chunk], show_progress: bool = False) -> dict[str, Any]:
    if not chunks:
        return {"backend": "chroma", "indexed": 0, "available": False, "reason": "no chunks"}

    try:
        collection = _get_collection(reset=True)
        batch_size = 128
        ranges = range(0, len(chunks), batch_size)
        if show_progress:
            try:
                from tqdm import tqdm

                ranges = tqdm(ranges, total=math.ceil(len(chunks) / batch_size), desc="Embedding chunks")
            except Exception:
                pass
        for start in ranges:
            batch = chunks[start : start + batch_size]
            collection.add(
                ids=[chunk.chunk_id for chunk in batch],
                documents=[chunk.text for chunk in batch],
                metadatas=[
                    {
                        "textbook_id": chunk.textbook_id,
                        "textbook": chunk.textbook,
                        "chapter": chunk.chapter,
                        "page": chunk.page,
                    }
                    for chunk in batch
                ],
            )
        return {"backend": "chroma", "indexed": len(chunks), "available": True}
    except Exception as exc:
        logger.warning("Chroma indexing failed, lexical retrieval remains available: %s", exc)
        return {"backend": "lexical", "indexed": len(chunks), "available": False, "reason": str(exc)}


def answer_query(question: str, chunks: list[Chunk], top_k: int = 5) -> RagAnswer:
    """RAG 问答入口：检索相关 chunk 并生成带引用的回答。

    检索策略：ChromaDB 向量检索 → BM25 词项检索 → 本地词项检索（fallback）。
    回答策略：LLM 生成 → 本地摘要 fallback。

    Args:
        question: 用户问题。
        chunks: 已索引的知识块列表。
        top_k: 检索返回的最大块数。

    Returns:
        RagAnswer 包含回答文本、引用列表和源文本。
    """
    if not chunks:
        return RagAnswer(answer="当前知识库中未找到相关信息", citations=[], source_chunks=[])

    # 混合检索：ChromaDB 向量 + BM25 词项，RRF 融合
    chroma_results = _retrieve_with_chroma(question, top_k * 2)
    bm25_results = _retrieve_bm25(question, chunks, top_k * 2)

    if chroma_results and bm25_results:
        ranked = _rrf_fuse(chroma_results, bm25_results, top_k)
    elif chroma_results:
        ranked = chroma_results[:top_k]
    else:
        ranked = _retrieve_lexical(question, chunks, top_k)

    ranked = [chunk for chunk in ranked if chunk.relevance_score > 0]

    if not ranked:
        return RagAnswer(answer="当前知识库中未找到相关信息", citations=[], source_chunks=[])

    citations = [
        {
            "textbook": chunk.textbook,
            "chapter": chunk.chapter,
            "page": chunk.page,
            "relevance_score": round(chunk.relevance_score, 3),
        }
        for chunk in ranked
    ]
    answer = _answer_with_llm(question, ranked)
    if answer is None:
        answer = _fallback_answer(ranked)
    return RagAnswer(answer=answer, citations=citations, source_chunks=[chunk.text for chunk in ranked])


def chroma_status() -> dict[str, Any]:
    try:
        collection = _get_collection(reset=False)
        return {
            "backend": "chroma",
            "available": True,
            "chunk_count": collection.count(),
            "embedding_model": settings.embedding_model,
            "db_dir": str(settings.chroma_db_dir),
        }
    except Exception as exc:
        return {
            "backend": "lexical",
            "available": False,
            "chunk_count": 0,
            "embedding_model": settings.embedding_model,
            "db_dir": str(settings.chroma_db_dir),
            "reason": str(exc),
        }


def external_medical_rag_status() -> dict[str, Any]:
    try:
        import sqlite3

        sqlite_path = settings.external_chroma_db_dir / "chroma.sqlite3"
        if not sqlite_path.exists():
            return {"available": False, "chunk_count": 0, "reason": "external chroma sqlite missing"}
        with sqlite3.connect(sqlite_path) as conn:
            count = conn.execute("select count(*) from embeddings").fetchone()[0]
        return {"available": True, "chunk_count": count, "db_dir": str(settings.external_chroma_db_dir)}
    except Exception as exc:
        return {"available": False, "chunk_count": 0, "reason": str(exc)}


def _retrieve_lexical(question: str, chunks: list[Chunk], top_k: int) -> list[Chunk]:
    return sorted(
        (chunk.model_copy(update={"relevance_score": _score(question, chunk.text)}) for chunk in chunks),
        key=lambda item: item.relevance_score,
        reverse=True,
    )[:top_k]


def _retrieve_bm25(question: str, chunks: list[Chunk], top_k: int) -> list[Chunk]:
    """使用 BM25Okapi 检索 top-k 相关块。

    Args:
        question: 用户问题文本。
        chunks: 已索引的知识块列表。
        top_k: 返回结果数。

    Returns:
        按 BM25 分数排序的 Chunk 列表，失败时返回空列表。
    """
    try:
        from rank_bm25 import BM25Okapi
    except ImportError:
        return []

    corpus = [_terms(chunk.text) for chunk in chunks]
    bm25 = BM25Okapi(corpus)
    scores = bm25.get_scores(_terms(question))
    ranked_indices = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)[:top_k]
    return [
        chunks[i].model_copy(update={"relevance_score": float(scores[i])})
        for i in ranked_indices
        if scores[i] > 0
    ]


def _rrf_fuse(list_a: list[Chunk], list_b: list[Chunk], top_k: int, k: int = 60) -> list[Chunk]:
    """Reciprocal Rank Fusion 合并两个排序列表。

    RRF score = Σ 1/(k + rank_i)，其中 k=60 是常数。

    Args:
        list_a: 第一个排序结果（如 ChromaDB 向量检索）。
        list_b: 第二个排序结果（如 BM25 词项检索）。
        top_k: 返回结果数。
        k: RRF 常数，默认 60。

    Returns:
        按 RRF 分数排序的 Chunk 列表。
    """
    score_map: dict[str, float] = {}
    chunk_map: dict[str, Chunk] = {}

    for rank, chunk in enumerate(list_a):
        score_map[chunk.chunk_id] = score_map.get(chunk.chunk_id, 0) + 1 / (k + rank)
        chunk_map[chunk.chunk_id] = chunk

    for rank, chunk in enumerate(list_b):
        score_map[chunk.chunk_id] = score_map.get(chunk.chunk_id, 0) + 1 / (k + rank)
        chunk_map[chunk.chunk_id] = chunk

    sorted_ids = sorted(score_map, key=lambda cid: score_map[cid], reverse=True)[:top_k]
    return [
        chunk_map[cid].model_copy(update={"relevance_score": score_map[cid]})
        for cid in sorted_ids
    ]


def _retrieve_with_chroma(question: str, top_k: int) -> list[Chunk] | None:
    """使用 ChromaDB 向量检索 top-k 相关块。

    Args:
        question: 用户问题文本。
        top_k: 返回结果数。

    Returns:
        按相关度排序的 Chunk 列表，检索失败时返回 None 触发 fallback。
    """
    try:
        collection = _get_collection(reset=False)
        if collection.count() == 0:
            return None
        result = collection.query(query_texts=[question], n_results=top_k)
    except Exception as exc:
        logger.warning("Chroma query failed, falling back to lexical retrieval: %s", exc)
        return None

    documents = result.get("documents", [[]])[0]
    metadatas = result.get("metadatas", [[]])[0]
    distances = result.get("distances", [[]])[0]
    ids = result.get("ids", [[]])[0]
    retrieved = []
    for index, text in enumerate(documents):
        metadata = metadatas[index] or {}
        distance = distances[index] if index < len(distances) else 1.0
        score = 1 / (1 + max(distance, 0))
        retrieved.append(
            Chunk(
                chunk_id=ids[index] if index < len(ids) else "",
                textbook_id=str(metadata.get("textbook_id", "")),
                textbook=str(metadata.get("textbook", "未知教材")),
                chapter=str(metadata.get("chapter", "未知章节")),
                page=int(metadata.get("page", 1) or 1),
                text=text,
                relevance_score=score,
            )
        )
    return retrieved


def _answer_with_llm(question: str, ranked: list[Chunk]) -> str | None:
    if not settings.llm_api_key:
        return None

    try:
        from openai import OpenAI
    except ImportError:
        return None

    context = "\n\n".join(
        (
            f"[{index}] 来源: {chunk.textbook}, {chunk.chapter}, 第 {chunk.page} 页, "
            f"相关度 {chunk.relevance_score:.3f}\n{chunk.text}"
        )
        for index, chunk in enumerate(ranked, start=1)
    )
    prompt = f"""你是一个严谨的教材 RAG 问答助手。请只基于给定教材片段回答问题。

要求：
1. 不要使用教材片段之外的知识。
2. 如果片段中没有答案，直接回复“当前知识库中未找到相关信息”。
3. 回答要简洁、教学可用。
4. 关键论断后用引用标记，格式为 [教材名称, 章节, 第 X 页]。
5. 不要编造页码、章节或教材名。

--- 教材片段 ---
{context}

--- 用户问题 ---
{question}
"""

    try:
        client = OpenAI(
            base_url=settings.llm_base_url,
            api_key=settings.llm_api_key,
            timeout=settings.rag_timeout_seconds,
        )
        response = client.chat.completions.create(
            model=settings.llm_model,
            messages=[
                {
                    "role": "system",
                    "content": "你只能基于用户提供的教材上下文回答，并必须保留来源引用。",
                },
                {"role": "user", "content": prompt},
            ],
            temperature=settings.rag_temperature,
            max_tokens=settings.rag_max_tokens,
        )
    except Exception as exc:
        logger.warning("RAG LLM call failed, using local fallback: %s", exc)
        return None

    msg = response.choices[0].message if response.choices else None
    content = msg.content if msg else ""
    # Fallback: some models (e.g. mimo) put output in reasoning_content
    if not content or not content.strip():
        content = getattr(msg, "reasoning_content", "") or ""
    return content.strip() or None


def _fallback_answer(ranked: list[Chunk]) -> str:
    evidence = "；".join(_first_sentence(chunk.text) for chunk in ranked[:2])
    refs = "、".join(f"[{chunk.textbook}, {chunk.chapter}, 第 {chunk.page} 页]" for chunk in ranked[:2])
    return f"基于当前教材证据：{evidence}。{refs}。以上回答由本地 fallback 生成，仅依据检索到的教材片段。"


def _score(question: str, text: str) -> float:
    q_terms = _terms(question)
    t_terms = _terms(text)
    if not q_terms or not t_terms:
        return 0.0
    q_counter = Counter(q_terms)
    t_counter = Counter(t_terms)
    common = set(q_counter) & set(t_counter)
    dot = sum(q_counter[t] * t_counter[t] for t in common)
    q_norm = math.sqrt(sum(v * v for v in q_counter.values()))
    t_norm = math.sqrt(sum(v * v for v in t_counter.values()))
    return dot / (q_norm * t_norm) if q_norm and t_norm else 0.0


def _terms(text: str) -> list[str]:
    chinese = re.findall(r"[\u4e00-\u9fa5]{2,}", text)
    latin = re.findall(r"[A-Za-z][A-Za-z0-9_-]{1,}", text.lower())
    grams = []
    for word in chinese:
        grams.extend(word[i : i + 2] for i in range(max(1, len(word) - 1)))
    return grams + latin


def _first_sentence(text: str) -> str:
    parts = re.split(r"[。！？]", text)
    return (parts[0] if parts else text)[:180]


def _get_collection(reset: bool):
    import chromadb
    from chromadb.config import Settings as ChromaSettings

    client = chromadb.PersistentClient(
        path=str(settings.chroma_db_dir),
        settings=ChromaSettings(anonymized_telemetry=False),
    )
    if reset:
        try:
            client.delete_collection(COLLECTION_NAME)
        except Exception:
            pass
    return client.get_or_create_collection(
        name=COLLECTION_NAME,
        embedding_function=_embedding_function(),
        metadata={"hnsw:space": "cosine"},
    )


@lru_cache(maxsize=1)
def _embedding_function():
    return SentenceTransformerEmbeddingFunction(settings.embedding_model)


class SentenceTransformerEmbeddingFunction:
    def __init__(self, model_name: str) -> None:
        from sentence_transformers import SentenceTransformer
        import torch

        # 自动检测设备：mps (Apple Silicon) -> cuda (NVIDIA) -> cpu
        if torch.backends.mps.is_available():
            device = "mps"
        elif torch.cuda.is_available():
            device = "cuda"
        else:
            device = "cpu"

        self.model = SentenceTransformer(model_name, device=device)

    def __call__(self, input: list[str]) -> list[list[float]]:
        vectors = self.model.encode(input, normalize_embeddings=True)
        return vectors.tolist()
