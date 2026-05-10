"use client";

import { ChangeEvent, useCallback, useEffect, useMemo, useState } from "react";
import type { ReactNode } from "react";
import { BookOpen, FileUp, GitMerge, MessageSquare, Network, RefreshCw, Search, Send, Sparkles } from "lucide-react";
import { GraphCanvas } from "@/components/GraphCanvas";
import { api } from "@/lib/api";
import type { KnowledgeNode, ProjectState, RagResponse } from "@/types/domain";

const initialState: ProjectState = {
  textbooks: [],
  graph: { nodes: [], edges: [] },
  decisions: [],
  chunks: [],
  chat_history: [],
  integrated_text: "",
  compression_ratio: 0
};

type PanelTab = "decisions" | "rag" | "chat" | "report";

export default function HomePage() {
  const [state, setState] = useState<ProjectState>(initialState);
  const [selectedNode, setSelectedNode] = useState<KnowledgeNode | null>(null);
  const [tab, setTab] = useState<PanelTab>("decisions");
  const [search, setSearch] = useState("");
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [question, setQuestion] = useState("炎症的核心概念是什么？");
  const [ragAnswer, setRagAnswer] = useState<RagResponse | null>(null);
  const [teacherMessage, setTeacherMessage] = useState("我觉得被删除的关键知识点应该保留，请更新整合方案。");
  const [report, setReport] = useState("");

  const refresh = useCallback(async () => {
    setState(await api.state());
  }, []);

  useEffect(() => {
    refresh().catch(() => undefined);
  }, [refresh]);

  const totals = useMemo(() => {
    const original = state.textbooks.reduce((sum, book) => sum + book.effective_chars, 0);
    const integrated = state.integrated_text.length;
    return {
      original,
      integrated,
      ratio: original ? integrated / original : state.compression_ratio,
      completed: state.textbooks.filter((book) => book.status === "completed").length
    };
  }, [state]);

  async function run<T>(label: string, task: () => Promise<T>, after?: (value: T) => void) {
    setBusy(label);
    setError(null);
    try {
      const value = await task();
      after?.(value);
      await refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : "操作失败");
    } finally {
      setBusy(null);
    }
  }

  function onFiles(event: ChangeEvent<HTMLInputElement>) {
    const files = event.target.files;
    if (!files?.length) return;
    void run("上传中", () => api.upload(files));
  }

  return (
    <main className="workspace">
      <header className="topbar">
        <div>
          <h1>学科知识整合智能体</h1>
          <p>多教材知识图谱、跨书去重提纯、RAG 精准问答与教师反馈迭代</p>
        </div>
        <div className="metrics">
          <Metric label="教材" value={`${totals.completed}/${state.textbooks.length}`} />
          <Metric label="节点" value={String(state.graph.nodes.length)} />
          <Metric label="关系" value={String(state.graph.edges.length)} />
          <Metric label="压缩比" value={`${(totals.ratio * 100).toFixed(1)}%`} warn={totals.ratio > 0.3} />
        </div>
      </header>

      <section className="shell">
        <aside className="left-panel">
          <label className="upload-zone">
            <FileUp size={24} />
            <strong>上传教材</strong>
            <span>PDF / Markdown / TXT / DOCX，支持批量</span>
            <input type="file" multiple accept=".pdf,.md,.markdown,.txt,.docx" onChange={onFiles} />
          </label>

          <div className="action-stack">
            <button onClick={() => run("解析中", () => api.parse())} disabled={!!busy || !state.textbooks.length}>
              <BookOpen size={16} /> 解析教材
            </button>
            <button onClick={() => run("建图中", () => api.buildGraph())} disabled={!!busy || !totals.completed}>
              <Network size={16} /> 构建图谱
            </button>
            <button onClick={() => run("整合中", () => api.mergeGraph())} disabled={!!busy || totals.completed < 2}>
              <GitMerge size={16} /> 跨教材整合
            </button>
            <button onClick={() => run("索引中", () => api.indexRag())} disabled={!!busy || !totals.completed}>
              <RefreshCw size={16} /> 建立 RAG 索引
            </button>
          </div>

          {busy && <div className="notice">{busy}...</div>}
          {error && <div className="error">{error}</div>}

          <div className="book-list">
            {state.textbooks.map((book) => (
              <article key={book.textbook_id} className="book-card">
                <div>
                  <strong>{book.title}</strong>
                  <span>{book.file_format.toUpperCase()} · {(book.size / 1024 / 1024).toFixed(2)} MB</span>
                </div>
                <em data-status={book.status}>{book.status}</em>
                <small>
                  {book.chapters.length} 章 · {book.effective_chars.toLocaleString()} 有效字
                </small>
              </article>
            ))}
          </div>
        </aside>

        <section className="center-panel">
          <div className="graph-toolbar">
            <div className="search-box">
              <Search size={16} />
              <input value={search} onChange={(event) => setSearch(event.target.value)} placeholder="搜索知识点并高亮节点" />
            </div>
            <span>节点大小表示跨教材频次，颜色表示教材来源</span>
          </div>
          <GraphCanvas graph={state.graph} selectedNode={selectedNode} search={search} onSelect={setSelectedNode} />
          {selectedNode && (
            <div className="node-detail">
              <button onClick={() => setSelectedNode(null)}>关闭</button>
              <h3>{selectedNode.name}</h3>
              <p>{selectedNode.definition}</p>
              <dl>
                <dt>类型</dt>
                <dd>{selectedNode.category}</dd>
                <dt>章节</dt>
                <dd>{selectedNode.chapter}</dd>
                <dt>来源</dt>
                <dd>{selectedNode.source_textbooks.join("、") || selectedNode.textbook_id}</dd>
              </dl>
            </div>
          )}
        </section>

        <aside className="right-panel">
          <nav className="tabs">
            <button data-active={tab === "decisions"} onClick={() => setTab("decisions")}>整合</button>
            <button data-active={tab === "rag"} onClick={() => setTab("rag")}>RAG</button>
            <button data-active={tab === "chat"} onClick={() => setTab("chat")}>对话</button>
            <button data-active={tab === "report"} onClick={() => setTab("report")}>报告</button>
          </nav>

          {tab === "decisions" && (
            <Panel title="整合决策" icon={<GitMerge size={16} />}>
              <div className="compression">
                <span>原始 {totals.original.toLocaleString()} 字</span>
                <span>整合 {totals.integrated.toLocaleString()} 字</span>
                <strong data-warn={totals.ratio > 0.3}>{(totals.ratio * 100).toFixed(1)}%</strong>
              </div>
              <div className="decision-list">
                {state.decisions.slice(0, 24).map((decision) => (
                  <article key={decision.decision_id}>
                    <header>
                      <b>{decision.action}</b>
                      <span>{Math.round(decision.confidence * 100)}%</span>
                    </header>
                    <p>{decision.reason}</p>
                    <small>{decision.affected_nodes.length} 个节点 · {decision.status}</small>
                  </article>
                ))}
              </div>
              {state.integrated_text && <pre className="integrated-text">{state.integrated_text}</pre>}
            </Panel>
          )}

          {tab === "rag" && (
            <Panel title="RAG 精准问答" icon={<Sparkles size={16} />}>
              <textarea value={question} onChange={(event) => setQuestion(event.target.value)} />
              <button onClick={() => run("检索中", () => api.queryRag(question), setRagAnswer)} disabled={!!busy || !question.trim()}>
                <Send size={16} /> 提问
              </button>
              {ragAnswer && (
                <div className="rag-answer">
                  <p>{ragAnswer.answer}</p>
                  {ragAnswer.citations.map((citation, index) => (
                    <details key={`${citation.textbook}-${index}`}>
                      <summary>
                        [{citation.textbook}, {citation.chapter}, 第 {citation.page} 页] · {citation.relevance_score}
                      </summary>
                      <span>{ragAnswer.source_chunks[index]}</span>
                    </details>
                  ))}
                </div>
              )}
            </Panel>
          )}

          {tab === "chat" && (
            <Panel title="教师多轮对话" icon={<MessageSquare size={16} />}>
              <div className="chat-history">
                {state.chat_history.map((message) => (
                  <p key={message.id} data-role={message.role}>{message.content}</p>
                ))}
              </div>
              <textarea value={teacherMessage} onChange={(event) => setTeacherMessage(event.target.value)} />
              <button onClick={() => run("反馈处理中", () => api.teacherChat(teacherMessage))} disabled={!!busy || !teacherMessage.trim()}>
                <Send size={16} /> 发送反馈
              </button>
            </Panel>
          )}

          {tab === "report" && (
            <Panel title="整合报告" icon={<BookOpen size={16} />}>
              <button onClick={() => run("生成报告中", () => api.generateReport(), (value) => setReport(value.content))} disabled={!!busy}>
                生成 report/整合报告.md
              </button>
              <pre className="report-preview">{report || "报告生成后会显示在这里，并写入后端 report/整合报告.md。"}</pre>
            </Panel>
          )}
        </aside>
      </section>
    </main>
  );
}

function Metric({ label, value, warn = false }: { label: string; value: string; warn?: boolean }) {
  return (
    <div className="metric" data-warn={warn}>
      <span>{label}</span>
      <strong>{value}</strong>
    </div>
  );
}

function Panel({ title, icon, children }: { title: string; icon: ReactNode; children: ReactNode }) {
  return (
    <section className="panel-section">
      <h2>{icon}{title}</h2>
      {children}
    </section>
  );
}
