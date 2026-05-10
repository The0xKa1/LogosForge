from __future__ import annotations

import json
import re
from pathlib import Path

import os

import requests
from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from .config import settings
from .models import ChatMessage, KnowledgeGraph, ParseStatus, Textbook, new_id
from .services.graph import build_graph_for_textbook, build_integrated_text, merge_graphs
from .services.parser import parse_textbook, save_upload
from .services.rag import answer_query, build_chunks, chroma_status, external_medical_rag_status, index_chunks
from .services.report import render_report
from .storage import store


PROJECT_ROOT = Path(__file__).resolve().parents[2]
UPLOAD_DIR = settings.upload_dir

# Allow CORS origins from env, comma-separated. Falls back to localhost dev origins.
_cors_env = os.getenv("CORS_ORIGINS", "")
ALLOWED_ORIGINS = (
    [o.strip() for o in _cors_env.split(",") if o.strip()]
    if _cors_env
    else [
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:3001",
        "http://127.0.0.1:3001",
        "http://localhost:3002",
        "http://127.0.0.1:3002",
    ]
)

app = FastAPI(title="Discipline Knowledge Integration Agent", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class ParseRequest(BaseModel):
    textbook_ids: list[str] | None = None


class GraphBuildRequest(BaseModel):
    textbook_ids: list[str] | None = None
    use_llm: bool = True


class RagQueryRequest(BaseModel):
    question: str


class TeacherChatRequest(BaseModel):
    message: str
    decision_id: str | None = None


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/api/state")
def get_state():
    return store.load()


@app.post("/api/reset")
def reset_state():
    return store.reset()


@app.post("/api/textbooks/upload")
async def upload_textbooks(files: list[UploadFile] = File(...)):
    state = store.load()
    uploaded = []
    for file in files:
        path = await save_upload(file, UPLOAD_DIR)
        book = Textbook(
            textbook_id=new_id("book"),
            filename=path.name,
            title=path.stem,
            file_format=path.suffix.lower().lstrip("."),
            size=path.stat().st_size,
            status=ParseStatus.uploaded,
        )
        state.textbooks = [existing for existing in state.textbooks if existing.filename != book.filename]
        state.textbooks.append(book)
        uploaded.append(book)
    store.save(state)
    return {"textbooks": uploaded}


@app.post("/api/textbooks/parse")
def parse_textbooks(request: ParseRequest):
    state = store.load()
    target_ids = set(request.textbook_ids or [book.textbook_id for book in state.textbooks])
    parsed = []
    for book in state.textbooks:
        if book.textbook_id not in target_ids:
            parsed.append(book)
            continue
        # 跳过已解析且有章节的教材（如通过导入脚本创建的）
        if book.status == ParseStatus.completed and book.chapters:
            parsed.append(book)
            continue
        path = UPLOAD_DIR / book.filename
        if not path.exists():
            book.status = ParseStatus.failed
            book.error = "Uploaded file missing"
            parsed.append(book)
            continue
        parsed_book = parse_textbook(path, textbook_id=book.textbook_id)
        if not parsed_book.textbook_id:
            parsed_book.textbook_id = book.textbook_id
        parsed.append(parsed_book)
    state.textbooks = parsed
    store.save(state)
    return {"textbooks": state.textbooks}


@app.post("/api/graph/build")
def build_graph(request: GraphBuildRequest):
    state = store.load()
    completed = [book for book in state.textbooks if book.status == ParseStatus.completed]

    # 确定要构建的教材
    if request.textbook_ids:
        target_ids = set(request.textbook_ids)
        books = [book for book in completed if book.textbook_id in target_ids]
    else:
        books = completed

    if not books:
        raise HTTPException(status_code=400, detail="No parsed textbooks available")

    # 逐本构建图谱，存入 state.graphs
    for book in books:
        graph = build_graph_for_textbook(book, use_llm=request.use_llm)
        state.graphs[book.textbook_id] = graph
        book.graph_built = True

    # 合并所有已构建的图谱
    all_graphs = list(state.graphs.values())
    if len(all_graphs) == 1:
        state.graph = all_graphs[0]
        state.decisions = []
    else:
        merged_graph, decisions = merge_graphs(all_graphs)
        state.graph = merged_graph
        state.decisions = decisions

    original_chars = sum(book.effective_chars for book in state.textbooks)
    state.integrated_text, state.compression_ratio = build_integrated_text(state.graph, original_chars)

    store.save(state)
    return {"graph": state.graph, "decisions": state.decisions, "integrated_text": state.integrated_text}


@app.post("/api/graph/merge")
def merge_all_graphs():
    state = store.load()
    books = [book for book in state.textbooks if book.status == ParseStatus.completed]
    if len(books) < 2:
        raise HTTPException(status_code=400, detail="At least two parsed textbooks are required")
    graphs = [build_graph_for_textbook(book) for book in books]
    graph, decisions = merge_graphs(graphs)
    original_chars = sum(book.effective_chars for book in books)
    state.graph = graph
    state.decisions = decisions
    state.integrated_text, state.compression_ratio = build_integrated_text(graph, original_chars)
    store.save(state)
    return {"graph": graph, "decisions": decisions, "integrated_text": state.integrated_text, "compression_ratio": state.compression_ratio}


@app.post("/api/rag/index")
def index_rag():
    state = store.load()
    state.chunks = build_chunks([book for book in state.textbooks if book.status == ParseStatus.completed])
    index_info = index_chunks(state.chunks)
    store.save(state)
    return {"indexed_textbooks": len(state.textbooks), "chunk_count": len(state.chunks), "index": index_info}


@app.get("/api/rag/status")
def rag_status():
    state = store.load()
    return {
        "indexed_textbooks": len([book for book in state.textbooks if book.status == ParseStatus.completed]),
        "chunk_count": len(state.chunks),
        "retriever": chroma_status(),
        "external_medical_rag": external_medical_rag_status(),
    }


@app.post("/api/rag/query")
def rag_query(request: RagQueryRequest):
    state = store.load()
    if not state.chunks:
        state.chunks = build_chunks([book for book in state.textbooks if book.status == ParseStatus.completed])
        store.save(state)
    return answer_query(request.question, state.chunks)


def _teacher_llm_reply(message: str, decisions: list, chat_history: list) -> tuple[str, list[dict]]:
    """使用 LLM 生成教师对话回复，返回 (回复文本, 决策修改列表)"""
    if not settings.llm_api_key:
        return "", []

    try:
        # 构建决策摘要
        decisions_summary = []
        for i, d in enumerate(decisions[:10]):  # 只取前10个决策
            decisions_summary.append(f"{i+1}. [{d.action}] {d.reason[:80]}...")

        decisions_text = "\n".join(decisions_summary) if decisions_summary else "暂无决策"

        # 构建对话历史
        history_text = ""
        if chat_history:
            recent_history = chat_history[-5:]  # 只取最近5条
            history_text = "\n".join([f"{msg.role}: {msg.content[:50]}" for msg in recent_history])

        prompt = f"""你是一个学科知识整合系统的 AI 助手，正在与教师对话。

教师的反馈：{message}

当前整合决策：
{decisions_text}

最近对话历史：
{history_text}

请根据教师的反馈，分析是否需要修改整合决策。如果需要，请返回 JSON 格式的修改建议：

{{
  "reply": "你的回复内容（要专业、友好、有帮助）",
  "modifications": [
    {{
      "decision_index": 0,
      "new_action": "keep/merge/remove",
      "reason": "修改原因"
    }}
  ]
}}

如果不需要修改决策，modifications 返回空数组。

要求：
1. 回复要专业、友好
2. 只在教师明确要求时才修改决策
3. 返回纯 JSON，不要有其他文字"""

        response = requests.post(
            f"{settings.llm_base_url}/chat/completions",
            headers={
                "Authorization": f"Bearer {settings.llm_api_key}",
                "Content-Type": "application/json"
            },
            json={
                "model": settings.llm_model,
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.3,
                "max_tokens": 2000,
            },
            timeout=30,
        )

        if response.status_code != 200:
            return "", []

        result = response.json()
        msg = result.get("choices", [{}])[0].get("message", {})
        content_text = msg.get("content", "")
        if not content_text.strip():
            content_text = msg.get("reasoning_content", "")

        # 解析 JSON
        json_match = re.search(r'\{.*\}', content_text, re.DOTALL)
        if not json_match:
            return "", []

        data = json.loads(json_match.group())
        reply = data.get("reply", "")
        modifications = data.get("modifications", [])

        return reply, modifications

    except Exception:
        return "", []


@app.post("/api/teacher/chat")
def teacher_chat(request: TeacherChatRequest):
    state = store.load()
    state.chat_history.append(ChatMessage(role="teacher", content=request.message))

    # 优先使用 LLM 版本
    llm_reply, modifications = _teacher_llm_reply(request.message, state.decisions, state.chat_history)

    changed = False
    if modifications:
        # 应用 LLM 返回的决策修改
        for mod in modifications:
            decision_index = mod.get("decision_index", -1)
            new_action = mod.get("new_action", "")
            reason = mod.get("reason", "")

            if 0 <= decision_index < len(state.decisions) and new_action in ["keep", "merge", "remove"]:
                decision = state.decisions[decision_index]
                if request.decision_id and decision.decision_id != request.decision_id:
                    continue
                decision.action = new_action
                decision.status = "overridden"
                decision.reason = f"教师反馈（AI分析）：{reason}"
                changed = True
    else:
        # LLM 未返回修改，使用关键词匹配作为 fallback
        for decision in state.decisions:
            if request.decision_id and decision.decision_id != request.decision_id:
                continue
            if any(keyword in request.message for keyword in ("保留", "不应该删除", "不要删除")) and decision.action == "remove":
                decision.action = "keep"
                decision.status = "overridden"
                decision.reason = f"教师反馈要求保留该知识点：{request.message}"
                changed = True
                break
            if any(keyword in request.message for keyword in ("分开", "不是同一个", "拆分")) and decision.action == "merge":
                decision.action = "keep"
                decision.status = "overridden"
                decision.reason = f"教师反馈要求拆分合并决策：{request.message}"
                changed = True
                break

    # 生成回复
    if llm_reply:
        reply = llm_reply
    elif changed:
        reply = "已根据教师反馈更新整合决策，并保留修改记录。"
    else:
        reply = "已记录教师反馈。当前反馈未命中可自动修改的决策，建议在决策列表中指定目标项。"

    state.chat_history.append(ChatMessage(role="agent", content=reply))
    store.save(state)
    return {"reply": reply, "decisions": state.decisions, "chat_history": state.chat_history}


@app.post("/api/report/generate")
def generate_report():
    state = store.load()
    content = render_report(state, PROJECT_ROOT)
    return {"path": str(PROJECT_ROOT / "report" / "整合报告.md"), "content": content}
