"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useCallback, useEffect, useState } from "react";
import ReaderChat from "@/components/ReaderChat";
import ReaderPane from "@/components/ReaderPane";
import { api } from "@/lib/api";
import { strings } from "@/lib/i18n";
import type { Language, WorkText } from "@/lib/types";

type Dock = "left" | "right";
type Tab = "read" | "chat";

const DOCK_STORAGE_KEY = "readerDock";

export default function ReadPage() {
  const { workId } = useParams<{ workId: string }>();
  const [work, setWork] = useState<WorkText | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [language, setLanguage] = useState<Language>("en");
  const [dock, setDock] = useState<Dock>(() => {
    if (typeof window === "undefined") return "right";
    const saved = window.localStorage.getItem(DOCK_STORAGE_KEY);
    return saved === "left" || saved === "right" ? saved : "right";
  });
  const [tab, setTab] = useState<Tab>("read");
  const [prefill, setPrefill] = useState<{ text: string; nonce: number } | null>(null);
  const s = strings(language);

  useEffect(() => {
    api
      .getWorkText(workId)
      .then(setWork)
      .catch((e) => setError(String(e)));
  }, [workId]);

  const toggleDock = () => {
    const next: Dock = dock === "right" ? "left" : "right";
    setDock(next);
    localStorage.setItem(DOCK_STORAGE_KEY, next);
  };

  const askAbout = useCallback((quote: string) => {
    const quoted = quote
      .split("\n")
      .map((line) => `> ${line}`)
      .join("\n");
    setPrefill((prev) => ({ text: `${quoted}\n\n`, nonce: (prev?.nonce ?? 0) + 1 }));
    setTab("chat"); // on mobile, jump to the composer
  }, []);

  return (
    <div className="flex h-screen flex-col">
      <nav className="flex shrink-0 items-center gap-3 border-b border-stone-800 px-4 py-2">
        <Link
          href="/library"
          className="text-sm text-stone-500 transition hover:text-amber-300"
        >
          {s.backToLibrary}
        </Link>
        <div className="ml-auto flex items-center gap-2">
          <button
            onClick={toggleDock}
            title={dock === "right" ? s.dockLeft : s.dockRight}
            className="hidden rounded-lg border border-stone-800 bg-stone-900 px-2.5 py-1.5 text-sm text-stone-400 transition hover:text-amber-300 md:block"
          >
            {dock === "right" ? "⇤" : "⇥"}
          </button>
          <div className="grid grid-cols-2 rounded-lg border border-stone-800 bg-stone-900 p-0.5 text-sm md:hidden">
            {(["read", "chat"] as const).map((t) => (
              <button
                key={t}
                onClick={() => setTab(t)}
                className={`rounded-md px-3 py-1.5 transition ${
                  tab === t
                    ? "bg-stone-800 text-stone-100"
                    : "text-stone-500 hover:text-stone-300"
                }`}
              >
                {t === "read" ? s.readTab : s.chatTab}
              </button>
            ))}
          </div>
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
      </nav>

      {!work && !error && <p className="p-6 text-sm text-stone-500">{s.loadingText}</p>}
      {error && (
        <p className="p-6 text-sm text-rose-400">
          {s.textLoadError} ({error})
        </p>
      )}

      {work && (
        <div className="flex min-h-0 flex-1">
          <div
            className={`min-w-0 flex-1 flex-col ${
              tab === "read" ? "flex" : "hidden"
            } md:flex ${dock === "left" ? "md:order-2" : ""}`}
          >
            <ReaderPane
              title={work.title}
              author={work.author}
              text={work.text}
              language={language}
              onAskSelection={askAbout}
            />
          </div>
          <div
            className={`min-w-0 flex-1 flex-col border-stone-800 ${
              tab === "chat" ? "flex" : "hidden"
            } md:flex md:w-2/5 md:flex-none ${
              dock === "right" ? "border-l" : "border-r md:order-1"
            }`}
          >
            <ReaderChat
              workId={work.id}
              author={work.author}
              personaId={work.persona_id}
              language={language}
              prefill={prefill}
            />
          </div>
        </div>
      )}
    </div>
  );
}
