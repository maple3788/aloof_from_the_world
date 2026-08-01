"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { personaTheme } from "@/lib/colors";
import { strings } from "@/lib/i18n";
import type { Language, PersonaDetail } from "@/lib/types";

export default function PersonaPage() {
  const { id } = useParams<{ id: string }>();
  const [persona, setPersona] = useState<PersonaDetail | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [language, setLanguage] = useState<Language>("en");
  const s = strings(language);

  useEffect(() => {
    api
      .getPersona(id)
      .then(setPersona)
      .catch((e) => setError(String(e)));
  }, [id]);

  const theme = personaTheme(persona?.id ?? "", persona?.color);
  const greeting =
    language === "zh" && persona?.greeting_zh ? persona.greeting_zh : persona?.greeting;

  return (
    <div className="mx-auto min-h-screen max-w-3xl px-6 py-10">
      <nav className="flex items-center">
        <Link
          href="/library"
          className="text-sm text-stone-500 transition hover:text-amber-300"
        >
          {s.backToLibrary}
        </Link>
        <div className="ml-auto grid grid-cols-2 rounded-lg border border-stone-800 bg-stone-900 p-0.5 text-sm">
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
      </nav>

      {!persona && !error && <p className="mt-6 text-sm text-stone-500">{s.loadingText}</p>}
      {error && (
        <p className="mt-6 text-sm text-rose-400">
          {s.personaNotFound} ({error})
        </p>
      )}

      {persona && (
        <>
          <header className={`mt-6 rounded-xl border p-5 ${theme.selected}`}>
            <p className="flex items-center gap-2 font-serif text-3xl font-semibold text-stone-100">
              <span className={`h-2.5 w-2.5 rounded-full ${theme.dot}`} />
              {persona.name}
            </p>
            <p className="mt-1 text-sm text-stone-500">
              {persona.tradition} · {persona.era} · {persona.authors.join(", ")}
            </p>
            <p className="mt-3 text-sm italic leading-relaxed text-stone-400">
              “{greeting}”
            </p>
            <Link
              href={`/?personas=${persona.id}`}
              className="mt-4 inline-block text-sm text-stone-400 transition hover:text-amber-300"
            >
              {s.startConversation}
            </Link>
          </header>

          <section className="mt-8">
            <h2 className="font-serif text-xl font-semibold text-stone-100">
              {s.personaVoice}
            </h2>
            <p className="mt-2 text-sm leading-relaxed text-stone-400">{persona.voice}</p>
          </section>

          <section className="mt-8">
            <h2 className="font-serif text-xl font-semibold text-stone-100">
              {s.personaWorldview}
            </h2>
            <p className="mt-2 text-sm leading-relaxed text-stone-400">
              {persona.worldview}
            </p>
          </section>

          <section className="mt-8">
            <h2 className="font-serif text-xl font-semibold text-stone-100">
              {s.personaStyleRules}
            </h2>
            <ul className="mt-2 list-inside list-disc space-y-1.5 text-sm leading-relaxed text-stone-400">
              {persona.style_rules.map((rule, i) => (
                <li key={i}>{rule}</li>
              ))}
            </ul>
          </section>

          <section className="mt-8">
            <h2 className="font-serif text-xl font-semibold text-stone-100">
              {s.personaWorks}
            </h2>
            <div className="mt-3 space-y-2">
              {persona.works.map((w) => (
                <div
                  key={w.id}
                  className="flex items-baseline justify-between gap-4 rounded-lg border border-stone-800 px-4 py-2.5"
                >
                  <div className="min-w-0">
                    <p className="truncate font-serif font-semibold text-stone-100">
                      {w.title}
                    </p>
                    <p className="text-xs text-stone-500">
                      {w.era}
                      {w.chunks > 0 ? ` · ${s.passages(w.chunks)}` : ""}
                    </p>
                  </div>
                  <Link
                    href={`/read/${w.id}`}
                    className="shrink-0 text-sm text-stone-500 transition hover:text-amber-300"
                  >
                    {s.readWork} →
                  </Link>
                </div>
              ))}
            </div>
          </section>
        </>
      )}
    </div>
  );
}
