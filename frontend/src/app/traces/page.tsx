"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import TraceBoard from "@/components/TraceBoard";
import { api } from "@/lib/api";
import { strings } from "@/lib/i18n";
import type { Language, Persona, Session, TraceSummary } from "@/lib/types";

export default function TracesPage() {
  const [traces, setTraces] = useState<TraceSummary[]>([]);
  const [sessions, setSessions] = useState<Session[]>([]);
  const [personas, setPersonas] = useState<Persona[]>([]);
  const [sessionFilter, setSessionFilter] = useState<string>("");
  const [language, setLanguage] = useState<Language>("en");
  const [error, setError] = useState<string | null>(null);

  const loadTraces = useCallback(
    (sessionId: string) => {
      api
        .listTraces(sessionId || undefined)
        .then(setTraces)
        .catch((e) => setError(String(e)));
    },
    [],
  );

  useEffect(() => {
    api.listSessions().then(setSessions).catch((e) => setError(String(e)));
    api.listPersonas().then(setPersonas).catch((e) => setError(String(e)));
  }, []);

  useEffect(() => {
    loadTraces(sessionFilter);
  }, [sessionFilter, loadTraces]);

  const s = strings(language);

  return (
    <div className="mx-auto min-h-screen max-w-5xl px-6 py-10">
      <Link href="/" className="text-sm text-stone-500 transition hover:text-amber-300">
        {s.backToConversations}
      </Link>

      <div className="mt-4 flex flex-wrap items-center gap-3">
        <h1 className="font-serif text-4xl font-semibold text-stone-100">
          {s.tracesTitle}
        </h1>
        <div className="ml-auto flex items-center gap-3">
          <select
            value={sessionFilter}
            onChange={(e) => setSessionFilter(e.target.value)}
            className="rounded-lg border border-stone-800 bg-stone-900 px-3 py-1.5 text-sm text-stone-300 outline-none focus:border-amber-700/70"
          >
            <option value="">{s.allSessions}</option>
            {sessions.map((sess) => (
              <option key={sess.id} value={sess.id}>
                {sess.title}
              </option>
            ))}
          </select>
          <div className="grid grid-cols-2 rounded-lg border border-stone-800 bg-stone-900 p-0.5 text-sm">
            {(["en", "zh"] as const).map((l) => (
              <button
                key={l}
                onClick={() => setLanguage(l)}
                className={`rounded-md px-2 py-1.5 transition ${
                  language === l
                    ? "bg-stone-800 text-stone-100"
                    : "text-stone-500 hover:text-stone-300"
                }`}
              >
                {l === "en" ? "EN" : "中文"}
              </button>
            ))}
          </div>
        </div>
      </div>
      <p className="mt-2 text-sm text-stone-500">{s.tracesSubtitle(traces.length)}</p>
      {error && <p className="mt-2 text-sm text-rose-400">{error}</p>}

      <TraceBoard
        traces={traces}
        sessions={sessions}
        personas={personas}
        language={language}
      />
    </div>
  );
}
