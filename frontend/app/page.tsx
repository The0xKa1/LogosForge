"use client";

import { ChangeEvent, useCallback, useEffect, useMemo, useState } from "react";
import type { ReactNode } from "react";
import { BookOpen, FileUp, GitMerge, MessageSquare, RefreshCw, Send, Sparkles } from "lucide-react";
import { NavBar } from "@/components/NavBar";
import { ProgressModal, type ProgressStep } from "@/components/ProgressModal";
import { api } from "@/lib/api";
import type { ProjectState, RagResponse } from "@/types/domain";

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
  const [tab, setTab] = useState<PanelTab>("decisions");
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [progressSteps, setProgressSteps] = useState<ProgressStep[]>([]);
  const [currentStep, setCurrentStep] = useState(0);
  const [question, setQuestion] = useState("炎症的核心概念是什么？");
  const [ragAnswer, setRagAnswer] = useState<RagResponse | null>(null);
  const [teacherMessage, setTeacherMessage] = useState("我觉得被删除的关键知识点应该保留，请更新整合方案。");
  const [report, setReport] = useState("");

  const refresh = useCallback(async () => {
    setState(await api.stateSummary());
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
      completed: state.textbooks.filter((book) => book.status === "completed").length,
      graphBuilt: state.textbooks.filter((book) => book.graph_built).length,
    };
  }, [state]);

  const STEP_CONFIGS: Record<string, ProgressStep[]> = {
    "上传中": [
      { label: "读取文件", detail: "正在读取本地文件..." },
      { label: "上传到服务器", detail: "正在传输文件..." },
      { label: "完成", detail: "上传成功" },
    ],
    "解析中": [
      { label: "读取教材", detail: "正在读取上传的文件..." },
      { label: "识别章节结构", detail: "正则匹配章节标题..." },
      { label: "提取内容", detail: "解析各章节文本..." },
      { label: "统计字数", detail: "计算有效字数..." },
      { label: "完成", detail: "解析完成" },
    ],
    "整合中": [
      { label: "构建各教材图谱", detail: "逐本生成知识点图谱..." },
      { label: "规范化知识点", detail: "同义词合并、去重..." },
      { label: "合并决策", detail: "生成 keep/merge/remove 决策..." },
      { label: "压缩整合文本", detail: "按 30% 压缩率生成整合内容..." },
      { label: "完成", detail: "整合完成" },
    ],
    "索引中": [
      { label: "构建分块", detail: "将教材章节切分为语义块..." },
      { label: "向量化", detail: "BGE 模型生成 embedding..." },
      { label: "写入 ChromaDB", detail: "建立向量索引..." },
      { label: "完成", detail: "RAG 索引就绪" },
    ],
    "检索中": [
      { label: "问题向量化", detail: "将问题转为向量..." },
      { label: "相似度检索", detail: "从 ChromaDB 检索相关片段..." },
      { label: "生成回答", detail: "调用 LLM 生成答案..." },
      { label: "完成", detail: "回答生成完成" },
    ],
    "反馈处理中": [
      { label: "分析教师反馈", detail: "调用 LLM 分析反馈意图..." },
      { label: "匹配决策", detail: "关联整合决策..." },
      { label: "生成回复", detail: "生成对话回复..." },
      { label: "完成", detail: "处理完成" },
    ],
    "生成报告中": [
      { label: "汇总数据", detail: "收集整合数据..." },
      { label: "生成报告", detail: "渲染 Markdown 报告..." },
      { label: "完成", detail: "报告生成完成" },
    ],
  };

  async function run<T>(label: string, task: () => Promise<T>, after?: (value: T) => void) {
    const steps = STEP_CONFIGS[label] || [{ label, detail: "处理中..." }];
    setBusy(label);
    setError(null);
    setProgressSteps(steps);
    setCurrentStep(0);
    let stepTimer: ReturnType<typeof setInterval> | undefined;
    try {
      stepTimer = setInterval(() => {
        setCurrentStep((prev) => {
          if (prev < steps.length - 2) return prev + 1;
          return prev;
        });
      }, label === "整合中" ? 15000 : 3000);

      const value = await task();
      clearInterval(stepTimer);
      setCurrentStep(steps.length - 1);
      after?.(value);
      await refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : "操作失败");
    } finally {
      if (stepTimer) clearInterval(stepTimer);
      setTimeout(() => {
        setBusy(null);
        setProgressSteps([]);
        setCurrentStep(0);
      }, 800);
    }
  }

  function onFiles(event: ChangeEvent<HTMLInputElement>) {
    const files = event.target.files;
    if (!files?.length) return;
    void run("上传中", () => api.upload(files));
  }

  return (
    <main className="workspace">
      <NavBar />

      <header className="topbar">
        <div className="brand-block">
          <h1>学科知识整合工作台</h1>
          <p>把多本教材压缩成可讲授、可追溯、可迭代的课程骨架。</p>
        </div>
        <div className="metrics">
          <Metric label="教材" value={`${totals.completed}/${state.textbooks.length}`} />
          <Metric label="已构建" value={`${totals.graphBuilt}/${state.textbooks.length}`} />
          <Metric label="节点" value={String(state.graph.nodes.length)} />
          <Metric label="压缩比" value={`${(totals.ratio * 100).toFixed(1)}%`} warn={totals.ratio > 0.3} />
        </div>
      </header>

      <section className="shell shell-two-col">
        <aside className="left-panel">
          <label className="upload-zone">
            <span className="upload-mark"><FileUp size={24} /></span>
            <strong>导入教材源</strong>
            <span>PDF / Markdown / TXT / DOCX，支持批量</span>
            <input type="file" multiple accept=".pdf,.md,.markdown,.txt,.docx" onChange={onFiles} />
          </label>

          <div className="action-stack">
            <button onClick={() => run("解析中", () => api.parse())} disabled={!!busy || !state.textbooks.length}>
              <BookOpen size={16} /> 解析教材
            </button>
            <button onClick={() => run("整合中", () => api.mergeGraph())} disabled={!!busy || totals.completed < 2}>
              <GitMerge size={16} /> 跨教材整合
            </button>
            <button onClick={() => run("索引中", () => api.indexRag())} disabled={!!busy || !totals.completed}>
              <RefreshCw size={16} /> 建立 RAG 索引
            </button>
          </div>

          {busy && (
            <ProgressModal
              title={busy}
              steps={progressSteps}
              currentStep={currentStep}
              error={error}
            />
          )}

          <div className="book-list">
            {!state.textbooks.length && (
              <div className="empty-list">
                <strong>还没有教材</strong>
                <span>先导入样例或上传文件，左侧流程会按解析、建图、整合、索引推进。</span>
              </div>
            )}
            {state.textbooks.map((book) => (
              <article key={book.textbook_id} className="book-card">
                <div className="book-info">
                  <strong>{book.title}</strong>
                  <span>{book.file_format.toUpperCase()} · {book.size > 0 ? `${(book.size / 1024 / 1024).toFixed(2)} MB` : `${(book.effective_chars / 1024).toFixed(0)}K 字`}</span>
                </div>
                <div className="book-badges">
                  <em data-status={book.status}>{book.status === "completed" ? "已解析" : book.status === "failed" ? "失败" : book.status}</em>
                  {book.graph_built && <em className="graph-badge">已构建</em>}
                </div>
                <small>
                  {(book.chapter_count ?? book.chapters.length).toLocaleString()} 章 · {book.effective_chars.toLocaleString()} 有效字
                </small>
              </article>
            ))}
          </div>
        </aside>

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
                {!state.decisions.length && (
                  <div className="empty-list">
                    <strong>等待整合决策</strong>
                    <span>解析至少两本教材后运行跨教材整合，这里会展示 merge / keep / remove。</span>
                  </div>
                )}
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
                {!state.chat_history.length && (
                  <p data-role="assistant">教师反馈会在这里沉淀为整合策略调整，并同步影响决策状态。</p>
                )}
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
