export type ParseStatus = "uploaded" | "parsing" | "completed" | "failed";

export interface Chapter {
  chapter_id: string;
  title: string;
  page_start: number;
  page_end: number;
  content: string;
  char_count: number;
}

export interface Textbook {
  textbook_id: string;
  filename: string;
  title: string;
  file_format: string;
  size: number;
  total_pages: number;
  total_chars: number;
  effective_chars: number;
  status: ParseStatus;
  error?: string | null;
  chapters: Chapter[];
  chapter_count?: number;
  graph_built?: boolean;
}

export interface KnowledgeNode {
  id: string;
  textbook_id: string;
  name: string;
  definition: string;
  category: string;
  chapter: string;
  page: number;
  frequency: number;
  source_textbooks: string[];
  evidence: string;
}

export interface KnowledgeEdge {
  id: string;
  source: string;
  target: string;
  relation_type: "prerequisite" | "parallel" | "contains" | "applies_to";
  description: string;
}

export interface KnowledgeGraph {
  textbook_id?: string | null;
  nodes: KnowledgeNode[];
  edges: KnowledgeEdge[];
}

export interface MergeDecision {
  decision_id: string;
  action: "merge" | "keep" | "remove";
  affected_nodes: string[];
  result_node?: string | null;
  reason: string;
  confidence: number;
  status: "active" | "overridden";
}

export interface ChatMessage {
  id: string;
  role: "teacher" | "agent";
  content: string;
  created_at: string;
}

export interface ProjectState {
  textbooks: Textbook[];
  graph: KnowledgeGraph;
  decisions: MergeDecision[];
  chunks: unknown[];
  chat_history: ChatMessage[];
  integrated_text: string;
  compression_ratio: number;
  summary?: {
    textbook_count: number;
    completed_textbook_count: number;
    chunk_count: number;
    node_count: number;
    edge_count: number;
    decision_count: number;
    original_effective_chars: number;
    integrated_chars: number;
  };
}

export interface RagResponse {
  answer: string;
  citations: Array<{
    textbook: string;
    chapter: string;
    page: number;
    relevance_score: number;
  }>;
  source_chunks: string[];
}
