"use client";

import { useState } from "react";
import { api } from "@/lib/api";
import { personaTheme } from "@/lib/colors";
import { strings, type Strings } from "@/lib/i18n";
import type {
  Language,
  Persona,
  Session,
  TraceDetail,
  TraceSummary,
} from "@/lib/types";

interface Props {
  traces: TraceSummary[];
  sessions: Session[];
  personas: Persona[];
  language: Language;
}

function personaLabel(personas: Persona[], id: string, s: Strings): string {
  if (id === "tutor") return s.tutorName;
  return personas.find((p) => p.id === id)?.name ?? id;
}

function SpeakerChips({
  ids,
  personas,
  s,
}: {
  ids: string[];
  personas: Persona[];
  s: Strings;
}) {
  return (
    <span className="flex flex-wrap gap-1">
      {ids.map((id) => {
        const theme = personaTheme(id, personas.find((p) => p.id === id)?.color);
        return (
          <span
            key={id}
            className={`inline-flex items-center gap-1 rounded-full border px-2 py-0.5 text-[11px] ${theme.selected}`}
          >
            <span className={`h-1.5 w-1.5 rounded-full ${theme.dot}`} />
            {personaLabel(personas, id, s)}
          </span>
        );
      })}
    </span>
  );
}

function DetailView({ detail, personas, s }: { detail: TraceDetail; personas: Persona[]; s: Strings }) {
  const d = detail.detail;
  return (
    <div className="space-y-3 border-t border-stone-800/60 px-4 py-3 text-xs">
      {d.translation_ms !== null && d.retrieval_query && (
        <p className="text-stone-400">
          <span className="text-stone-500">{s.traceTranslatedQuery}: </span>
          <span className="italic">“{d.retrieval_query}”</span>
          <span className="ml-1 tabular-nums text-stone-600">{d.translation_ms} ms</span>
        </p>
      )}

      {d.retrievals.map((r, i) => (
        <div key={`ret-${i}`}>
          <p className="text-stone-500">
            {s.traceRetrieval} · {personaLabel(personas, r.persona, s)} ·{" "}
            <span className="tabular-nums">{r.ms} ms</span> · {r.docs.length}
          </p>
          <ul className="mt-1 space-y-1">
            {r.docs.map((doc, j) => (
              <li key={j} className="rounded border border-stone-800 bg-stone-900/60 px-2 py-1.5">
                <span className="font-serif text-stone-300">{doc.title}</span>
                <span className="text-stone-500"> — {doc.author}</span>
                <span className="block mt-0.5 text-stone-600">{doc.excerpt}</span>
              </li>
            ))}
          </ul>
        </div>
      ))}

      {d.replies.map((r, i) => (
        <p key={`rep-${i}`} className="text-stone-500">
          {s.traceReply} · {personaLabel(personas, r.persona, s)} ·{" "}
          <span className="tabular-nums">{r.ms} ms</span> · {r.chars} chars
        </p>
      ))}

      {d.critic.map((c, i) => (
        <p key={`cri-${i}`} className="text-stone-500">
          {s.traceCritic} · {personaLabel(personas, c.persona, s)} ·{" "}
          {c.supported === true ? (
            <span className="text-emerald-400">{s.traceSupported}</span>
          ) : c.supported === false ? (
            <span className="text-amber-300">{s.traceOverreach}</span>
          ) : (
            <span>{s.traceNoVerdict}</span>
          )}
          {c.citations > 0 && <span> · {c.citations} cites</span>}
          {c.from_cache && <span className="text-stone-600"> · {s.traceCacheHit}</span>}
          {c.note && <span className="block mt-0.5 italic text-stone-400">{c.note}</span>}
        </p>
      ))}

      {detail.status === "error" && detail.error && (
        <p className="rounded border border-rose-800/50 bg-rose-950/40 px-2 py-1.5 text-rose-300">
          {s.traceErrorLabel}: {detail.error}
        </p>
      )}
    </div>
  );
}

export default function TraceBoard({ traces, sessions, personas, language }: Props) {
  const s = strings(language);
  const [expandedId, setExpandedId] = useState<string | null>(null);
  const [details, setDetails] = useState<Record<string, TraceDetail>>({});
  const [loadingId, setLoadingId] = useState<string | null>(null);

  const sessionTitle = (id: string) =>
    sessions.find((sess) => sess.id === id)?.title ?? id;

  const toggle = async (id: string) => {
    if (expandedId === id) {
      setExpandedId(null);
      return;
    }
    setExpandedId(id);
    if (!details[id]) {
      setLoadingId(id);
      try {
        const detail = await api.getTrace(id);
        setDetails((prev) => ({ ...prev, [id]: detail }));
      } finally {
        setLoadingId(null);
      }
    }
  };

  if (traces.length === 0) {
    return <p className="mt-6 text-sm text-stone-600">{s.tracesEmpty}</p>;
  }

  return (
    <div className="mt-6 divide-y divide-stone-800/60 overflow-hidden rounded-xl border border-stone-800">
      {traces.map((t) => {
        const expanded = expandedId === t.id;
        const detail = details[t.id];
        return (
          <div key={t.id} className="bg-stone-900/30">
            <button
              onClick={() => toggle(t.id)}
              className="flex w-full items-center gap-3 px-4 py-3 text-left transition hover:bg-stone-800/40"
            >
              <span
                className={`h-2 w-2 shrink-0 rounded-full ${
                  t.status === "ok"
                    ? "bg-emerald-400"
                    : t.status === "error"
                      ? "bg-rose-400"
                      : "bg-stone-500"
                }`}
                title={t.status === "aborted" ? s.traceStatusAborted : t.status}
              />
              <span className="min-w-0 flex-1">
                <span className="block truncate text-sm text-stone-200">{t.query}</span>
                <span className="mt-0.5 flex flex-wrap items-center gap-x-2 gap-y-1 text-[11px] text-stone-600">
                  <span>{t.mode === "study" ? "◦" : "◆"}</span>
                  <span>{t.language === "zh" ? "中文" : "EN"}</span>
                  <span className="truncate">{sessionTitle(t.session_id)}</span>
                  <span className="tabular-nums">
                    {new Date(t.created_at).toLocaleString(
                      language === "zh" ? "zh-CN" : "en-US",
                      { month: "short", day: "numeric", hour: "2-digit", minute: "2-digit" },
                    )}
                  </span>
                </span>
              </span>
              <SpeakerChips ids={t.speakers} personas={personas} s={s} />
              <span className="shrink-0 tabular-nums text-xs text-stone-500">
                {(t.total_ms / 1000).toFixed(1)}s
              </span>
              <span className="shrink-0 text-stone-600">{expanded ? "▾" : "▸"}</span>
            </button>
            {expanded && (
              loadingId === t.id || !detail ? (
                <p className="border-t border-stone-800/60 px-4 py-3 text-xs text-stone-600">
                  {s.thinking}
                </p>
              ) : (
                <DetailView detail={detail} personas={personas} s={s} />
              )
            )}
          </div>
        );
      })}
    </div>
  );
}
