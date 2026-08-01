export interface Persona {
  id: string;
  name: string;
  era: string;
  tradition: string;
  color: string;
  greeting: string;
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
  persona_ids: string[];
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
}

export interface AgentResponse {
  responder: string;
  responder_name: string;
  content: string;
  citations: Citation[];
  critic_note: string | null;
}

export type StreamEvent =
  | { type: "start"; mode: string; persona_ids: string[] }
  | { type: "token"; persona: string; content: string }
  | { type: "done"; responses: AgentResponse[] }
  | { type: "error"; detail: string };
