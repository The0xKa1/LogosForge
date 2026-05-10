"use client";

import { useCallback, useEffect, useState } from "react";
import { Network } from "lucide-react";
import { GraphCanvas } from "@/components/GraphCanvas";
import { NavBar } from "@/components/NavBar";
import { ProgressModal, type ProgressStep } from "@/components/ProgressModal";
import { api } from "@/lib/api";
import type { KnowledgeNode, ProjectState } from "@/types/domain";

const initialState: ProjectState = {
  textbooks: [],
  graph: { nodes: [], edges: [] },
  decisions: [],
  chunks: [],
  chat_history: [],
  integrated_text: "",
  compression_ratio: 0
};

export default function GraphPage() {
  const [state, setState] = useState<ProjectState>(initialState);
  const [selectedNode, setSelectedNode] = useState<KnowledgeNode | null>(null);
  const [search, setSearch] = useState("");
  const [selectedBooks, setSelectedBooks] = useState<Set<string>>(new Set());
  const [useLlm, setUseLlm] = useState(true);
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [progressSteps, setProgressSteps] = useState<ProgressStep[]>([]);
  const [currentStep, setCurrentStep] = useState(0);

  const refresh = useCallback(async () => {
    setState(await api.state());
  }, []);

  useEffect(() => {
    refresh().catch(() => undefined);
  }, [refresh]);

  const STEP_CONFIGS: Record<string, ProgressStep[]> = {
    "建图中": [
      { label: "加载教材", detail: "读取已解析的教材数据..." },
      { label: "抽取知识点", detail: "逐章提取核心概念..." },
      { label: "推断关系", detail: "分析知识点间的语义关系..." },
      { label: "构建图谱", detail: "生成节点与边..." },
      { label: "完成", detail: "图谱构建完成" },
    ],
  };

  async function run<T>(label: string, task: () => Promise<T>) {
    const steps = STEP_CONFIGS[label] || [{ label, detail: "处理中..." }];
    setBusy(label);
    setError(null);
    setProgressSteps(steps);
    setCurrentStep(0);
    try {
      const stepTimer = setInterval(() => {
        setCurrentStep((prev) => (prev < steps.length - 2 ? prev + 1 : prev));
      }, 15000);

      await task();
      clearInterval(stepTimer);
      setCurrentStep(steps.length - 1);
      await refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : "操作失败");
    } finally {
      setTimeout(() => {
        setBusy(null);
        setProgressSteps([]);
        setCurrentStep(0);
      }, 800);
    }
  }

  const completedBooks = state.textbooks.filter((b) => b.status === "completed");

  return (
    <main className="workspace">
      <NavBar />

      <header className="topbar graph-topbar">
        <div className="graph-controls-bar">
          <div className="graph-book-select">
            {completedBooks.map((book) => (
              <label key={book.textbook_id} className="graph-book-chip">
                <input
                  type="checkbox"
                  checked={selectedBooks.has(book.textbook_id)}
                  onChange={(e) => {
                    setSelectedBooks((prev) => {
                      const next = new Set(prev);
                      if (e.target.checked) next.add(book.textbook_id);
                      else next.delete(book.textbook_id);
                      return next;
                    });
                  }}
                />
                <span>{book.title}</span>
                {book.graph_built && <em className="chip-badge">已构建</em>}
              </label>
            ))}
          </div>
          <div className="graph-actions">
            <label className="llm-toggle">
              <input
                type="checkbox"
                checked={useLlm}
                onChange={(e) => setUseLlm(e.target.checked)}
              />
              <span>LLM</span>
            </label>
            <button
              className="build-btn"
              onClick={() => {
                const ids = selectedBooks.size > 0 ? Array.from(selectedBooks) : undefined;
                run("建图中", () => api.buildGraph(ids, useLlm));
              }}
              disabled={!!busy || !completedBooks.length}
            >
              <Network size={16} />
              {selectedBooks.size > 0 ? `构建 (${selectedBooks.size})` : "构建全部"}
            </button>
          </div>
        </div>
      </header>

      {busy && (
        <ProgressModal
          title={busy}
          steps={progressSteps}
          currentStep={currentStep}
          error={error}
        />
      )}

      <section className="graph-page-body">
        <GraphCanvas
          graph={state.graph}
          selectedNode={selectedNode}
          search={search}
          onSelect={setSelectedNode}
          onSearchChange={setSearch}
        />
      </section>
    </main>
  );
}
