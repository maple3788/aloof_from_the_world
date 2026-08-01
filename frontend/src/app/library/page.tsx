"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { personaTheme } from "@/lib/colors";
import type { Persona, Work } from "@/lib/types";

function readLabel(work: Work, personas: Persona[]): string {
  const name = personas.find((p) => p.id === work.persona_id)?.name;
  return name ? `Read with ${name}` : "Read";
}

export default function LibraryPage() {
  const [personas, setPersonas] = useState<Persona[]>([]);
  const [works, setWorks] = useState<Work[]>([]);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api.listPersonas().then(setPersonas).catch((e) => setError(String(e)));
    api.listWorks().then(setWorks).catch((e) => setError(String(e)));
  }, []);

  const totalChunks = works.reduce((sum, w) => sum + w.chunks, 0);

  return (
    <div className="mx-auto min-h-screen max-w-5xl px-6 py-10">
      <Link href="/" className="text-sm text-stone-500 transition hover:text-amber-300">
        ← Back to conversations
      </Link>

      <h1 className="mt-4 font-serif text-4xl font-semibold text-stone-100">
        The Library
      </h1>
      <p className="mt-2 text-sm text-stone-500">
        {works.length} works · {totalChunks.toLocaleString()} indexed passages. Every
        answer the thinkers give is retrieved from these texts.
      </p>
      {error && <p className="mt-2 text-sm text-rose-400">{error}</p>}

      <h2 className="mt-10 font-serif text-2xl font-semibold text-stone-100">
        The Speakers
      </h2>
      <div className="mt-4 grid gap-4 sm:grid-cols-2">
        {personas.map((p) => {
          const theme = personaTheme(p.id, p.color);
          return (
            <div key={p.id} className={`rounded-xl border p-4 ${theme.selected}`}>
              <p className="flex items-center gap-2 font-serif text-lg font-semibold text-stone-100">
                <span className={`h-2 w-2 rounded-full ${theme.dot}`} />
                {p.name}
              </p>
              <p className="mt-0.5 text-xs text-stone-500">
                {p.tradition} · {p.era}
              </p>
              <p className="mt-2 text-sm italic leading-relaxed text-stone-400">
                “{p.greeting}”
              </p>
            </div>
          );
        })}
      </div>

      <h2 className="mt-10 font-serif text-2xl font-semibold text-stone-100">
        The Corpus
      </h2>
      <div className="mt-4 overflow-hidden rounded-xl border border-stone-800">
        <table className="w-full text-left text-sm">
          <thead className="bg-stone-900 text-xs uppercase tracking-wider text-stone-500">
            <tr>
              <th className="px-4 py-3">Work</th>
              <th className="px-4 py-3">Author</th>
              <th className="px-4 py-3">Tradition</th>
              <th className="px-4 py-3">Era</th>
              <th className="px-4 py-3 text-right">Passages</th>
              <th className="px-4 py-3 text-right"></th>
            </tr>
          </thead>
          <tbody className="divide-y divide-stone-800/60">
            {works.map((w) => (
              <tr key={w.id} className="text-stone-300">
                <td className="px-4 py-2.5 font-serif font-semibold text-stone-100">
                  {w.title}
                </td>
                <td className="px-4 py-2.5">{w.author}</td>
                <td className="px-4 py-2.5 text-stone-500">{w.tradition}</td>
                <td className="px-4 py-2.5 text-stone-500">{w.era}</td>
                <td className="px-4 py-2.5 text-right tabular-nums text-stone-500">
                  {w.chunks > 0 ? w.chunks.toLocaleString() : "—"}
                </td>
                <td className="px-4 py-2.5 text-right">
                  <Link
                    href={`/read/${w.id}`}
                    className="text-xs text-stone-500 transition hover:text-amber-300"
                  >
                    {readLabel(w, personas)} →
                  </Link>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <p className="mt-3 text-xs text-stone-600">
        All texts are public domain, sourced from Project Gutenberg. Add more with the
        ingestion CLI (see README).
      </p>
    </div>
  );
}
