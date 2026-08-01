"use client";

import Link from "next/link";
import type { Persona, Session } from "@/lib/types";
import PersonaPicker from "./PersonaPicker";

interface Props {
  personas: Persona[];
  sessions: Session[];
  activeSessionId: string | null;
  draftMode: "discuss" | "study";
  draftPersonas: string[];
  maxPersonas: number;
  onModeChange: (mode: "discuss" | "study") => void;
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
  draftPersonas,
  maxPersonas,
  onModeChange,
  onTogglePersona,
  onNewChat,
  onSelectSession,
  onDeleteSession,
}: Props) {
  const active = sessions.find((s) => s.id === activeSessionId);
  const locked = Boolean(active);

  return (
    <aside className="flex h-full w-72 shrink-0 flex-col border-r border-stone-800 bg-stone-900/40">
      <div className="border-b border-stone-800 px-4 py-4">
        <h1 className="font-serif text-xl font-semibold tracking-wide text-stone-100">
          Aloof from the World
        </h1>
        <p className="mt-0.5 text-xs text-stone-500">
          Conversations with the dead greats, grounded in their books.
        </p>
      </div>

      <div className="flex-1 space-y-4 overflow-y-auto px-4 py-4 scrollbar-thin">
        <button
          onClick={onNewChat}
          className="w-full rounded-lg border border-amber-700/50 bg-amber-500/10 px-3 py-2 text-sm font-medium text-amber-200 transition hover:bg-amber-500/20"
        >
          + New conversation
        </button>

        <PersonaPicker
          personas={personas}
          mode={active ? active.mode : draftMode}
          selected={active ? active.persona_ids : draftPersonas}
          maxPersonas={maxPersonas}
          locked={locked}
          onModeChange={onModeChange}
          onToggle={onTogglePersona}
        />
        {locked && (
          <p className="text-xs text-stone-600">
            Mode and speakers are set per conversation. Start a new one to change them.
          </p>
        )}

        <div className="space-y-1 pt-2">
          <p className="text-xs font-medium uppercase tracking-wider text-stone-600">
            History
          </p>
          {sessions.length === 0 && (
            <p className="text-xs text-stone-600">No conversations yet.</p>
          )}
          {sessions.map((s) => (
            <div
              key={s.id}
              className={`group flex items-center rounded-lg border transition ${
                s.id === activeSessionId
                  ? "border-stone-700 bg-stone-800/60"
                  : "border-transparent hover:bg-stone-800/40"
              }`}
            >
              <button
                onClick={() => onSelectSession(s.id)}
                className="flex-1 truncate px-3 py-2 text-left text-sm text-stone-300"
                title={s.title}
              >
                <span className="mr-1.5 text-stone-600">
                  {s.mode === "study" ? "◦" : "◆"}
                </span>
                {s.title}
              </button>
              <button
                onClick={() => onDeleteSession(s.id)}
                className="mr-2 hidden text-stone-600 hover:text-rose-400 group-hover:block"
                title="Delete conversation"
              >
                ×
              </button>
            </div>
          ))}
        </div>
      </div>

      <div className="border-t border-stone-800 px-4 py-3">
        <Link
          href="/library"
          className="text-sm text-stone-400 transition hover:text-amber-300"
        >
          → Browse the library
        </Link>
      </div>
    </aside>
  );
}
