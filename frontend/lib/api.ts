import type { ProjectState, RagResponse } from "@/types/domain";

const API_BASE = process.env.NODE_ENV === "production" ? "" : process.env.NEXT_PUBLIC_API_BASE ?? "";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, {
    ...init,
    headers: init?.body instanceof FormData ? init.headers : { "Content-Type": "application/json", ...init?.headers }
  });
  if (!response.ok) {
    const detail = await response.text();
    throw new Error(detail || `Request failed: ${response.status}`);
  }
  return response.json() as Promise<T>;
}

export const api = {
  state: () => request<ProjectState>("/api/state"),
  stateSummary: () => request<ProjectState>("/api/state/summary"),
  upload: (files: FileList) => {
    const form = new FormData();
    Array.from(files).forEach((file) => form.append("files", file));
    return request<{ textbooks: ProjectState["textbooks"] }>("/api/textbooks/upload", { method: "POST", body: form });
  },
  parse: () => request<{ textbooks: ProjectState["textbooks"] }>("/api/textbooks/parse", { method: "POST", body: JSON.stringify({}) }),
  buildGraph: (textbookIds?: string[], useLlm: boolean = true) => request<Pick<ProjectState, "graph" | "decisions" | "integrated_text">>("/api/graph/build", { method: "POST", body: JSON.stringify({ textbook_ids: textbookIds ?? null, use_llm: useLlm }) }),
  mergeGraph: () => request<Pick<ProjectState, "graph" | "decisions" | "integrated_text" | "compression_ratio">>("/api/graph/merge", { method: "POST" }),
  indexRag: () => request<{ indexed_textbooks: number; chunk_count: number }>("/api/rag/index", { method: "POST" }),
  ragStatus: () => request<{ indexed_textbooks: number; chunk_count: number }>("/api/rag/status"),
  queryRag: (question: string) => request<RagResponse>("/api/rag/query", { method: "POST", body: JSON.stringify({ question }) }),
  teacherChat: (message: string, decisionId?: string) =>
    request<Pick<ProjectState, "decisions" | "chat_history"> & { reply: string }>("/api/teacher/chat", {
      method: "POST",
      body: JSON.stringify({ message, decision_id: decisionId })
    }),
  generateReport: () => request<{ path: string; content: string }>("/api/report/generate", { method: "POST" })
};
