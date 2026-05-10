from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from .models import ChatMessage, KnowledgeGraph, ParseStatus, Textbook, new_id
from .services.graph import build_graph_for_textbook, build_integrated_text, merge_graphs
from .services.parser import parse_textbook, save_upload
from .services.rag import answer_query, build_chunks, chroma_status, external_medical_rag_status, index_chunks
from .services.report import render_report
from .storage import store


PROJECT_ROOT = Path(__file__).resolve().parents[2]
UPLOAD_DIR = PROJECT_ROOT / "uploads"

app = FastAPI(title="Discipline Knowledge Integration Agent", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class ParseRequest(BaseModel):
    textbook_ids: list[str] | None = None


class GraphBuildRequest(BaseModel):
    textbook_id: str | None = None


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
    books = [book for book in state.textbooks if book.status == ParseStatus.completed]
    if request.textbook_id:
        books = [book for book in books if book.textbook_id == request.textbook_id]
    if not books:
        raise HTTPException(status_code=400, detail="No parsed textbooks available")

    graphs = [build_graph_for_textbook(book) for book in books]
    if request.textbook_id:
        graph = graphs[0]
        state.graph = graph
        state.decisions = []
    else:
        graph, decisions = merge_graphs(graphs)
        state.graph = graph
        state.decisions = decisions
        original_chars = sum(book.effective_chars for book in state.textbooks)
        state.integrated_text, state.compression_ratio = build_integrated_text(graph, original_chars)
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


@app.post("/api/teacher/chat")
def teacher_chat(request: TeacherChatRequest):
    state = store.load()
    state.chat_history.append(ChatMessage(role="teacher", content=request.message))
    changed = False
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
    reply = "已根据教师反馈更新整合决策，并保留修改记录。" if changed else "已记录教师反馈。当前反馈未命中可自动修改的决策，建议在决策列表中指定目标项。"
    state.chat_history.append(ChatMessage(role="agent", content=reply))
    store.save(state)
    return {"reply": reply, "decisions": state.decisions, "chat_history": state.chat_history}


@app.post("/api/report/generate")
def generate_report():
    state = store.load()
    content = render_report(state, PROJECT_ROOT)
    return {"path": str(PROJECT_ROOT / "report" / "整合报告.md"), "content": content}
