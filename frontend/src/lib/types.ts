export type Language = "en" | "zh";

export interface Persona {
  id: string;
  name: string;
  era: string;
  tradition: string;
  color: string;
  greeting: string;
  greeting_zh?: string;
}

export interface Health {
  status: string;
  llm_provider: string;
  embedding_provider: string;
  max_personas: number;
  cache: string;
}

export interface Citation {
  work_id: string;
  title: string;
  author: string;
  era: string;
  chunk_index: number;
  excerpt: string;
}

export interface Message {
  id?: number;
  role: "user" | "assistant";
  persona_id?: string | null;
  content: string;
  citations?: Citation[];
  critic_note?: string | null;
  streaming?: boolean;
}

export interface Session {
  id: string;
  title: string;
  mode: "discuss" | "study";
  language: Language;
  persona_ids: string[];
  work_id?: string | null;
  created_at: string;
  messages?: Message[];
}

export interface Work {
  id: string;
  title: string;
  author: string;
  tradition: string;
  era: string;
  gutenberg_id: number;
  chunks: number;
  persona_id: string | null;
}

export interface WorkText {
  id: string;
  title: string;
  author: string;
  persona_id: string | null;
  chars: number;
  text: string;
}

export interface AgentResponse {
  responder: string;
  responder_name: string;
  content: string;
  citations: Citation[];
  critic_note: string | null;
}

export type TraceStatus = "ok" | "error" | "aborted";

export interface TraceSummary {
  id: string;
  session_id: string;
  query: string;
  mode: "discuss" | "study";
  language: Language;
  speakers: string[];
  status: TraceStatus;
  error: string | null;
  total_ms: number;
  created_at: string;
}

export interface TraceRetrieval {
  persona: string;
  ms: number;
  docs: Citation[];
}

export interface TraceReply {
  persona: string;
  ms: number;
  chars: number;
}

export interface TraceCriticVerdict {
  persona: string;
  supported: boolean | null;
  note: string | null;
  citations: number;
  from_cache: boolean;
}

export interface TraceDetail extends TraceSummary {
  detail: {
    retrieval_query: string | null;
    translation_ms: number | null;
    retrievals: TraceRetrieval[];
    replies: TraceReply[];
    critic: TraceCriticVerdict[];
  };
}

export type StreamEvent =
  | { type: "start"; mode: string; language?: Language; persona_ids: string[] }
  | { type: "token"; persona: string; content: string }
  | { type: "done"; trace_id?: string; responses: AgentResponse[] }
  | { type: "error"; detail: string };
