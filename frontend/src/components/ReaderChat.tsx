"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import Composer from "./Composer";
import MessageList from "./MessageList";
import { api, streamChat } from "@/lib/api";
import { personaTheme } from "@/lib/colors";
import { strings } from "@/lib/i18n";
import type { Language, Message, Persona } from "@/lib/types";

type SummonState = "ready" | "summoning" | "failed";

interface Props {
  workId: string;
  author: string;
  /** Matched persona for the work's author; null triggers the persona forge. */
  personaId: string | null;
  language: Language;
  prefill: { text: string; nonce: number } | null;
}

export default function ReaderChat({
  workId,
  author,
  personaId,
  language,
  prefill,
}: Props) {
  const [persona, setPersona] = useState<Persona | null>(null);
  const [summon, setSummon] = useState<SummonState>(
    personaId ? "ready" : "summoning",
  );
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [messages, setMessages] = useState<Message[]>([]);
  const [streaming, setStreaming] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const streamAbortRef = useRef<AbortController | null>(null);
  const s = strings(language);

  const runSummon = useCallback(() => {
    api
      .generatePersona(workId)
      .then((card) => {
        setPersona(card);
        setSummon("ready");
      })
      .catch(() => setSummon("failed"));
  }, [workId]);

  const retrySummon = () => {
    setSummon("summoning");
    runSummon();
  };

  useEffect(() => {
    let cancelled = false;
    if (personaId) {
      api
        .listPersonas()
        .then((list) => {
          if (cancelled) return;
          const found = list.find((p) => p.id === personaId) ?? null;
          setPersona(found);
          setSummon(found ? "ready" : "failed");
        })
        .catch(() => {
          if (!cancelled) setSummon("failed");
        });
    } else {
      runSummon();
    }
    return () => {
      cancelled = true;
    };
  }, [personaId, runSummon]);

  // Abort the in-flight stream on unmount.
  useEffect(() => {
    return () => streamAbortRef.current?.abort();
  }, []);

  const send = useCallback(
    async (text: string) => {
      if (streaming || !persona) return;
      setError(null);
      setStreaming(true);
      try {
        let sid = sessionId;
        if (!sid) {
          const created = await api.createSession(
            "discuss",
            [persona.id],
            language,
            workId,
          );
          setSessionId(created.id);
          sid = created.id;
        }

        setMessages((prev) => [...prev, { role: "user", content: text }]);
        const streamIndex = new Map<string, number>();
        const controller = new AbortController();
        streamAbortRef.current = controller;

        await streamChat(
          sid,
          text,
          (event) => {
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
          },
          controller.signal,
        );
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
    [streaming, persona, sessionId, language, workId],
  );

  const theme = personaTheme(persona?.id ?? "", persona?.color);
  const greeting =
    language === "zh" && persona?.greeting_zh ? persona.greeting_zh : persona?.greeting;

  return (
    <div className="flex min-h-0 flex-1 flex-col">
      <header className="shrink-0 border-b border-stone-800 px-4 py-3">
        {persona ? (
          <div className="flex items-center gap-2">
            <span className={`h-2 w-2 shrink-0 rounded-full ${theme.dot}`} />
            <div className="min-w-0">
              <p className="truncate font-serif text-base font-semibold text-stone-100">
                {persona.name}
              </p>
              <p className="truncate text-xs text-stone-500">{persona.era}</p>
            </div>
          </div>
        ) : (
          <p className="truncate font-serif text-base text-stone-300">{author}</p>
        )}
      </header>

      {summon === "summoning" && (
        <div className="flex flex-1 flex-col items-center justify-center gap-3 px-6 text-center">
          <p className="animate-pulse font-serif text-lg text-stone-200">
            {s.summoning(author)}
          </p>
          <p className="max-w-xs text-xs leading-relaxed text-stone-500">
            {s.summoningHint}
          </p>
        </div>
      )}

      {summon === "failed" && (
        <div className="flex flex-1 flex-col items-center justify-center gap-3 px-6 text-center">
          <p className="text-sm text-stone-400">{s.summonFailed}</p>
          <button
            onClick={retrySummon}
            className="rounded-lg border border-amber-700/50 bg-amber-500/10 px-3 py-1.5 text-sm text-amber-200 transition hover:bg-amber-500/20"
          >
            {s.retrySummon}
          </button>
        </div>
      )}

      {summon === "ready" && persona && (
        <>
          {error && (
            <div className="border-b border-rose-800/50 bg-rose-950/40 px-4 py-2 text-sm text-rose-300">
              {error} — {s.backendError}
            </div>
          )}
          {messages.length === 0 ? (
            <div className="flex flex-1 items-center justify-center px-6">
              <div className={`w-full max-w-sm rounded-xl border p-4 ${theme.selected}`}>
                <p className="text-sm italic leading-relaxed text-stone-400">
                  “{greeting}”
                </p>
              </div>
            </div>
          ) : (
            <MessageList messages={messages} personas={[persona]} language={language} />
          )}
          <Composer
            disabled={streaming}
            language={language}
            placeholder={s.placeholderReading(persona.name)}
            onSend={send}
            prefill={prefill}
          />
        </>
      )}
    </div>
  );
}
