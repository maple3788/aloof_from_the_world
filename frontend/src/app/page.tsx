"use client";

import { useCallback, useEffect, useState } from "react";
import Composer from "@/components/Composer";
import MessageList from "@/components/MessageList";
import Sidebar from "@/components/Sidebar";
import { api, streamChat } from "@/lib/api";
import { personaTheme } from "@/lib/colors";
import type { Message, Persona, Session } from "@/lib/types";

const TUTOR_GREETING =
  "Welcome. Tell me what you are studying — a thinker, a movement, a period — and I will explain it, question you on it, or quiz you, drawing on the library's texts.";

export default function Home() {
  const [personas, setPersonas] = useState<Persona[]>([]);
  const [sessions, setSessions] = useState<Session[]>([]);
  const [activeSessionId, setActiveSessionId] = useState<string | null>(null);
  const [messages, setMessages] = useState<Message[]>([]);
  const [draftMode, setDraftMode] = useState<"discuss" | "study">("discuss");
  const [draftPersonas, setDraftPersonas] = useState<string[]>(["socrates"]);
  const [streaming, setStreaming] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api.listPersonas().then(setPersonas).catch((e) => setError(String(e)));
    api.listSessions().then(setSessions).catch((e) => setError(String(e)));
  }, []);

  const activeSession = sessions.find((s) => s.id === activeSessionId) ?? null;
  const currentMode = activeSession?.mode ?? draftMode;
  const currentPersonas = activeSession?.persona_ids ?? draftPersonas;

  const selectSession = useCallback(async (id: string) => {
    setError(null);
    setActiveSessionId(id);
    try {
      const detail = await api.getSession(id);
      setMessages(detail.messages ?? []);
    } catch (e) {
      setError(String(e));
    }
  }, []);

  const newChat = useCallback(() => {
    setActiveSessionId(null);
    setMessages([]);
    setError(null);
  }, []);

  const deleteSession = useCallback(
    async (id: string) => {
      await api.deleteSession(id).catch((e) => setError(String(e)));
      setSessions((prev) => prev.filter((s) => s.id !== id));
      if (id === activeSessionId) newChat();
    },
    [activeSessionId, newChat],
  );

  const toggleDraftPersona = useCallback((id: string) => {
    setDraftPersonas((prev) =>
      prev.includes(id)
        ? prev.filter((p) => p !== id)
        : prev.length < 3
          ? [...prev, id]
          : prev,
    );
  }, []);

  const send = useCallback(
    async (text: string) => {
      if (streaming) return;
      setError(null);
      setStreaming(true);

      let sessionId = activeSessionId;
      try {
        if (!sessionId) {
          const created = await api.createSession(
            draftMode,
            draftMode === "study" ? [] : draftPersonas,
          );
          setSessions((prev) => [created, ...prev]);
          setActiveSessionId(created.id);
          sessionId = created.id;
        }

        setMessages((prev) => [...prev, { role: "user", content: text }]);
        const streamIndex = new Map<string, number>();

        await streamChat(sessionId, text, (event) => {
          if (event.type === "token") {
            setMessages((prev) => {
              const next = [...prev];
              let idx = streamIndex.get(event.persona);
              if (idx === undefined) {
                idx = next.length;
                streamIndex.set(event.persona, idx);
                next.push({
                  role: "assistant",
                  persona_id: event.persona,
                  content: "",
                  streaming: true,
                });
              }
              next[idx] = { ...next[idx], content: next[idx].content + event.content };
              return next;
            });
          } else if (event.type === "done") {
            setMessages((prev) => [
              ...prev.filter((m) => !m.streaming),
              ...event.responses.map((r) => ({
                role: "assistant" as const,
                persona_id: r.responder,
                content: r.content,
                citations: r.citations,
                critic_note: r.critic_note,
              })),
            ]);
          } else if (event.type === "error") {
            setError(event.detail);
          }
        });

        api.listSessions().then(setSessions).catch(() => {});
      } catch (e) {
        setError(String(e));
        setMessages((prev) =>
          prev.map((m) => (m.streaming ? { ...m, streaming: false } : m)),
        );
      } finally {
        setStreaming(false);
      }
    },
    [streaming, activeSessionId, draftMode, draftPersonas],
  );

  const showWelcome = messages.length === 0;
  const greetingPersonas = personas.filter((p) => currentPersonas.includes(p.id));

  return (
    <div className="flex h-screen">
      <Sidebar
        personas={personas}
        sessions={sessions}
        activeSessionId={activeSessionId}
        draftMode={draftMode}
        draftPersonas={draftPersonas}
        onModeChange={setDraftMode}
        onTogglePersona={toggleDraftPersona}
        onNewChat={newChat}
        onSelectSession={selectSession}
        onDeleteSession={deleteSession}
      />

      <main className="flex min-w-0 flex-1 flex-col">
        {error && (
          <div className="border-b border-rose-800/50 bg-rose-950/40 px-6 py-2 text-sm text-rose-300">
            {error} — is the backend running? (uv run uvicorn app.main:app --reload)
          </div>
        )}

        {showWelcome ? (
          <div className="flex flex-1 flex-col items-center justify-center gap-8 overflow-y-auto px-6 py-10">
            <div className="text-center">
              <h2 className="font-serif text-4xl font-semibold text-stone-100">
                {currentMode === "study"
                  ? "Study with the Tutor"
                  : greetingPersonas.length > 1
                    ? "Convene a roundtable"
                    : "Begin the dialogue"}
              </h2>
              <p className="mt-2 max-w-md text-sm text-stone-500">
                {currentMode === "study"
                  ? TUTOR_GREETING
                  : "Ask about virtue, dreams, power, the Tao — every answer is drawn from the primary texts in the library."}
              </p>
            </div>
            {currentMode === "discuss" && (
              <div className="flex max-w-3xl flex-wrap justify-center gap-4">
                {greetingPersonas.map((p) => {
                  const theme = personaTheme(p.id, p.color);
                  return (
                    <div
                      key={p.id}
                      className={`w-72 rounded-xl border p-4 ${theme.selected}`}
                    >
                      <p className="flex items-center gap-2 font-serif text-lg font-semibold text-stone-100">
                        <span className={`h-2 w-2 rounded-full ${theme.dot}`} />
                        {p.name}
                      </p>
                      <p className="mt-0.5 text-xs text-stone-500">{p.era}</p>
                      <p className="mt-2 text-sm italic leading-relaxed text-stone-400">
                        “{p.greeting}”
                      </p>
                    </div>
                  );
                })}
              </div>
            )}
          </div>
        ) : (
          <MessageList messages={messages} personas={personas} />
        )}

        <Composer
          disabled={streaming}
          placeholder={
            currentMode === "study"
              ? "Ask for an explanation, a Socratic dialogue, or a quiz…"
              : currentPersonas.length > 1
                ? "Pose a question to the roundtable…"
                : "Ask your question…"
          }
          onSend={send}
        />
      </main>
    </div>
  );
}
