"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import Composer from "@/components/Composer";
import MessageList from "@/components/MessageList";
import Sidebar from "@/components/Sidebar";
import { api, streamChat } from "@/lib/api";
import { personaTheme } from "@/lib/colors";
import { strings } from "@/lib/i18n";
import type { Language, Message, Persona, Session } from "@/lib/types";

export default function Home() {
  const [personas, setPersonas] = useState<Persona[]>([]);
  const [sessions, setSessions] = useState<Session[]>([]);
  const [activeSessionId, setActiveSessionId] = useState<string | null>(null);
  const [messages, setMessages] = useState<Message[]>([]);
  const [draftMode, setDraftMode] = useState<"discuss" | "study">("discuss");
  const [draftLanguage, setDraftLanguage] = useState<Language>("en");
  const [draftPersonas, setDraftPersonas] = useState<string[]>(["socrates"]);
  const [maxPersonas, setMaxPersonas] = useState(3);
  const [streaming, setStreaming] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const streamAbortRef = useRef<AbortController | null>(null);
  const sessionFetchAbortRef = useRef<AbortController | null>(null);

  // Abort the in-flight stream/session fetch on unmount.
  useEffect(() => {
    return () => {
      streamAbortRef.current?.abort();
      sessionFetchAbortRef.current?.abort();
    };
  }, []);

  useEffect(() => {
    api.listPersonas().then(setPersonas).catch((e) => setError(String(e)));
    api.listSessions().then(setSessions).catch((e) => setError(String(e)));
    api
      .getHealth()
      .then((h) => setMaxPersonas(h.max_personas))
      .catch(() => {});
  }, []);

  const activeSession = sessions.find((s) => s.id === activeSessionId) ?? null;
  const currentMode = activeSession?.mode ?? draftMode;
  const currentLanguage = activeSession?.language ?? draftLanguage;
  const currentPersonas = activeSession?.persona_ids ?? draftPersonas;
  const s = strings(currentLanguage);

  const selectSession = useCallback(async (id: string) => {
    // Switching sessions must kill any in-flight stream, or its tokens
    // would keep rendering into the newly selected session's messages.
    streamAbortRef.current?.abort();
    sessionFetchAbortRef.current?.abort();
    const controller = new AbortController();
    sessionFetchAbortRef.current = controller;
    setError(null);
    setActiveSessionId(id);
    try {
      const detail = await api.getSession(id, controller.signal);
      if (controller.signal.aborted) return;
      setMessages(detail.messages ?? []);
    } catch (e) {
      if (e instanceof DOMException && e.name === "AbortError") return;
      setError(String(e));
    }
  }, []);

  const newChat = useCallback(() => {
    streamAbortRef.current?.abort();
    sessionFetchAbortRef.current?.abort();
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

  const toggleDraftPersona = useCallback(
    (id: string) => {
      setDraftPersonas((prev) =>
        prev.includes(id)
          ? prev.filter((p) => p !== id)
          : prev.length < maxPersonas
            ? [...prev, id]
            : prev,
      );
    },
    [maxPersonas],
  );

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
            draftLanguage,
          );
          setSessions((prev) => [created, ...prev]);
          setActiveSessionId(created.id);
          sessionId = created.id;
        }

        setMessages((prev) => [...prev, { role: "user", content: text }]);
        const streamIndex = new Map<string, number>();
        const controller = new AbortController();
        streamAbortRef.current = controller;

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
        }, controller.signal);

        api.listSessions().then(setSessions).catch(() => {});
      } catch (e) {
        if (!(e instanceof DOMException && e.name === "AbortError")) {
          setError(String(e));
          setMessages((prev) =>
            prev.map((m) => (m.streaming ? { ...m, streaming: false } : m)),
          );
        }
      } finally {
        streamAbortRef.current = null;
        setStreaming(false);
      }
    },
    [streaming, activeSessionId, draftMode, draftPersonas, draftLanguage],
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
        draftLanguage={draftLanguage}
        draftPersonas={draftPersonas}
        maxPersonas={maxPersonas}
        onModeChange={setDraftMode}
        onLanguageChange={setDraftLanguage}
        onTogglePersona={toggleDraftPersona}
        onNewChat={newChat}
        onSelectSession={selectSession}
        onDeleteSession={deleteSession}
      />

      <main className="flex min-w-0 flex-1 flex-col">
        {error && (
          <div className="border-b border-rose-800/50 bg-rose-950/40 px-6 py-2 text-sm text-rose-300">
            {error} — {s.backendError}
          </div>
        )}

        {showWelcome ? (
          <div className="flex flex-1 flex-col items-center justify-center gap-8 overflow-y-auto px-6 py-10">
            <div className="text-center">
              <h2 className="font-serif text-4xl font-semibold text-stone-100">
                {currentMode === "study"
                  ? s.welcomeStudy
                  : greetingPersonas.length > 1
                    ? s.welcomeRoundtable
                    : s.welcomeDialogue}
              </h2>
              <p className="mt-2 max-w-md text-sm text-stone-500">
                {currentMode === "study" ? s.tutorGreeting : s.welcomeDiscussHint}
              </p>
            </div>
            {currentMode === "discuss" && (
              <div className="flex max-w-3xl flex-wrap justify-center gap-4">
                {greetingPersonas.map((p) => {
                  const theme = personaTheme(p.id, p.color);
                  const greeting =
                    currentLanguage === "zh" && p.greeting_zh
                      ? p.greeting_zh
                      : p.greeting;
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
                        “{greeting}”
                      </p>
                    </div>
                  );
                })}
              </div>
            )}
          </div>
        ) : (
          <MessageList
            messages={messages}
            personas={personas}
            language={currentLanguage}
          />
        )}

        <Composer
          disabled={streaming}
          language={currentLanguage}
          placeholder={
            currentMode === "study"
              ? s.placeholderStudy
              : currentPersonas.length > 1
                ? s.placeholderRoundtable
                : s.placeholderAsk
          }
          onSend={send}
        />
      </main>
    </div>
  );
}
