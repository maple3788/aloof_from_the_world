"use client";

import Link from "next/link";
import { strings } from "@/lib/i18n";
import type { Language, Persona, Session } from "@/lib/types";
import PersonaPicker from "./PersonaPicker";

interface Props {
  personas: Persona[];
  sessions: Session[];
  activeSessionId: string | null;
  draftMode: "discuss" | "study";
  draftLanguage: Language;
  draftPersonas: string[];
  maxPersonas: number;
  onModeChange: (mode: "discuss" | "study") => void;
  onLanguageChange: (language: Language) => void;
  onTogglePersona: (id: string) => void;
  onNewChat: () => void;
  onSelectSession: (id: string) => void;
  onDeleteSession: (id: string) => void;
}

export default function Sidebar({
  personas,
  sessions,
  activeSessionId,
  draftMode,
  draftLanguage,
  draftPersonas,
  maxPersonas,
  onModeChange,
  onLanguageChange,
  onTogglePersona,
  onNewChat,
  onSelectSession,
  onDeleteSession,
}: Props) {
  const active = sessions.find((s) => s.id === activeSessionId);
  const locked = Boolean(active);
  const language: Language = active?.language ?? draftLanguage;
  const s = strings(language);

  return (
    <aside className="flex h-full w-72 shrink-0 flex-col border-r border-stone-800 bg-stone-900/40">
      <div className="border-b border-stone-800 px-4 py-4">
        <h1 className="font-serif text-xl font-semibold tracking-wide text-stone-100">
          Aloof from the World
        </h1>
        <p className="mt-0.5 text-xs text-stone-500">{s.tagline}</p>
      </div>

      <div className="flex-1 space-y-4 overflow-y-auto px-4 py-4 scrollbar-thin">
        <button
          onClick={onNewChat}
          className="w-full rounded-lg border border-amber-700/50 bg-amber-500/10 px-3 py-2 text-sm font-medium text-amber-200 transition hover:bg-amber-500/20"
        >
          {s.newConversation}
        </button>

        <PersonaPicker
          personas={personas}
          mode={active ? active.mode : draftMode}
          language={language}
          selected={active ? active.persona_ids : draftPersonas}
          maxPersonas={maxPersonas}
          locked={locked}
          onModeChange={onModeChange}
          onLanguageChange={onLanguageChange}
          onToggle={onTogglePersona}
        />
        {locked && <p className="text-xs text-stone-600">{s.lockedHint}</p>}

        <div className="space-y-1 pt-2">
          <p className="text-xs font-medium uppercase tracking-wider text-stone-600">
            {s.history}
          </p>
          {sessions.length === 0 && (
            <p className="text-xs text-stone-600">{s.emptyHistory}</p>
          )}
          {sessions.map((session) => (
            <div
              key={session.id}
              className={`group flex items-center rounded-lg border transition ${
                session.id === activeSessionId
                  ? "border-stone-700 bg-stone-800/60"
                  : "border-transparent hover:bg-stone-800/40"
              }`}
            >
              <button
                onClick={() => onSelectSession(session.id)}
                className="flex min-w-0 flex-1 items-center px-3 py-2 text-left text-sm text-stone-300"
                title={session.title}
              >
                <span className="mr-1.5 text-stone-600">
                  {session.mode === "study" ? "◦" : "◆"}
                </span>
                <span className="truncate">{session.title}</span>
                <span className="ml-1.5 shrink-0 text-[10px] text-stone-600">
                  {session.language === "zh" ? "中文" : "EN"}
                </span>
              </button>
              <button
                onClick={() => onDeleteSession(session.id)}
                className="mr-2 hidden text-stone-600 hover:text-rose-400 group-hover:block"
                title="Delete conversation"
              >
                ×
              </button>
            </div>
          ))}
        </div>
      </div>

      <div className="space-y-1.5 border-t border-stone-800 px-4 py-3">
        <Link
          href="/library"
          className="block text-sm text-stone-400 transition hover:text-amber-300"
        >
          {s.browseLibrary}
        </Link>
        <Link
          href="/traces"
          className="block text-sm text-stone-400 transition hover:text-amber-300"
        >
          {s.traceBoard}
        </Link>
      </div>
    </aside>
  );
}
