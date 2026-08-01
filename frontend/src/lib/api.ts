import type {
  Health,
  Language,
  Persona,
  PersonaDetail,
  Session,
  StreamEvent,
  TraceDetail,
  TraceSummary,
  UploadResult,
  Work,
  WorkText,
} from "./types";

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export class AmbiguousMatchError extends Error {
  candidate: Persona;

  constructor(candidate: Persona) {
    super("Author nearly matches an existing persona");
    this.candidate = candidate;
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API_URL}${path}`, {
    headers: { "Content-Type": "application/json" },
    ...init,
  });
  if (!res.ok) {
    throw new Error(`${init?.method ?? "GET"} ${path} failed: ${res.status}`);
  }
  if (res.status === 204) return undefined as T;
  return res.json() as Promise<T>;
}

export const api = {
  listSessions: () => request<Session[]>("/sessions"),
  createSession: (mode: string, personaIds: string[], language: Language, workId?: string) =>
    request<Session>("/sessions", {
      method: "POST",
      body: JSON.stringify({
        mode,
        persona_ids: personaIds,
        language,
        ...(workId ? { work_id: workId } : {}),
      }),
    }),
  getSession: (id: string, signal?: AbortSignal) =>
    request<Session>(`/sessions/${id}`, { signal }),
  deleteSession: (id: string) =>
    request<void>(`/sessions/${id}`, { method: "DELETE" }),
  listPersonas: () => request<Persona[]>("/personas"),
  getPersona: (id: string) => request<PersonaDetail>(`/personas/${id}`),
  generatePersona: (workId: string) =>
    request<Persona>("/personas/generate", {
      method: "POST",
      body: JSON.stringify({ work_id: workId }),
    }),
  listWorks: () => request<Work[]>("/library/works"),
  getWorkText: (workId: string) => request<WorkText>(`/library/works/${workId}/text`),
  uploadWork: async (form: FormData): Promise<UploadResult> => {
    // No JSON content-type: the browser sets the multipart boundary.
    const res = await fetch(`${API_URL}/library/uploads`, { method: "POST", body: form });
    if (res.status === 409) {
      const body = (await res.json()) as { candidate: Persona };
      throw new AmbiguousMatchError(body.candidate);
    }
    if (!res.ok) {
      throw new Error(`POST /library/uploads failed: ${res.status}`);
    }
    return res.json() as Promise<UploadResult>;
  },
  getHealth: () => request<Health>("/health"),
  listTraces: (sessionId?: string, limit = 50, offset = 0) => {
    const params = new URLSearchParams({ limit: String(limit), offset: String(offset) });
    if (sessionId) params.set("session_id", sessionId);
    return request<TraceSummary[]>(`/traces?${params}`);
  },
  getTrace: (id: string) => request<TraceDetail>(`/traces/${id}`),
};

export async function streamChat(
  sessionId: string,
  message: string,
  onEvent: (event: StreamEvent) => void,
  signal?: AbortSignal,
): Promise<void> {
  const res = await fetch(`${API_URL}/chat/stream`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ session_id: sessionId, message }),
    signal,
  });
  if (!res.ok || !res.body) {
    throw new Error(`chat stream failed: ${res.status}`);
  }

  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  for (;;) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });

    let sep: number;
    while ((sep = buffer.indexOf("\n\n")) !== -1) {
      const frame = buffer.slice(0, sep);
      buffer = buffer.slice(sep + 2);
      for (const line of frame.split("\n")) {
        if (!line.startsWith("data:")) continue;
        const payload = line.slice(5).trim();
        if (!payload) continue;
        try {
          onEvent(JSON.parse(payload) as StreamEvent);
        } catch {
          // malformed frame mid-stream: skip rather than kill the chat
        }
      }
    }
  }
}
