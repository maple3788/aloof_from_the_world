"use client";

import type { Persona } from "@/lib/types";
import { personaTheme } from "@/lib/colors";

interface Props {
  personas: Persona[];
  mode: "discuss" | "study";
  selected: string[];
  maxPersonas: number;
  locked: boolean;
  onModeChange: (mode: "discuss" | "study") => void;
  onToggle: (id: string) => void;
}

export default function PersonaPicker({
  personas,
  mode,
  selected,
  maxPersonas,
  locked,
  onModeChange,
  onToggle,
}: Props) {
  return (
    <div className="space-y-3">
      <div className="grid grid-cols-2 rounded-lg border border-stone-800 bg-stone-900 p-0.5 text-sm">
        {(["discuss", "study"] as const).map((m) => (
          <button
            key={m}
            disabled={locked}
            onClick={() => onModeChange(m)}
            className={`rounded-md px-2 py-1.5 capitalize transition ${
              mode === m
                ? "bg-stone-800 text-stone-100"
                : "text-stone-500 hover:text-stone-300"
            } disabled:opacity-50`}
          >
            {m}
          </button>
        ))}
      </div>

      {mode === "discuss" ? (
        <div className="space-y-1.5">
          <p className="text-xs text-stone-500">
            Choose up to {maxPersonas} thinkers ({selected.length}/{maxPersonas})
            {selected.length > 1 && " — roundtable"}
          </p>
          {personas.map((p) => {
            const theme = personaTheme(p.id, p.color);
            const active = selected.includes(p.id);
            return (
              <button
                key={p.id}
                disabled={locked || (!active && selected.length >= maxPersonas)}
                onClick={() => onToggle(p.id)}
                className={`w-full rounded-lg border px-3 py-2 text-left transition disabled:opacity-50 ${
                  active
                    ? theme.selected
                    : "border-stone-800 bg-stone-900 hover:border-stone-700"
                }`}
              >
                <span className="flex items-center gap-2">
                  <span className={`h-2 w-2 rounded-full ${theme.dot}`} />
                  <span className="font-serif text-sm font-semibold text-stone-100">
                    {p.name}
                  </span>
                </span>
                <span className="mt-0.5 block text-xs text-stone-500">
                  {p.tradition} · {p.era}
                </span>
              </button>
            );
          })}
        </div>
      ) : (
        <div className="rounded-lg border border-teal-800/40 bg-teal-500/5 px-3 py-2">
          <p className="font-serif text-sm font-semibold text-teal-200">The Tutor</p>
          <p className="mt-0.5 text-xs text-stone-500">
            Explanations, Socratic questions, and quizzes grounded in the library.
          </p>
        </div>
      )}
    </div>
  );
}
