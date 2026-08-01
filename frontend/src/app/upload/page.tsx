"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { AmbiguousMatchError, api } from "@/lib/api";
import { strings } from "@/lib/i18n";
import type { Language, Persona, UploadResult } from "@/lib/types";

type Phase = "form" | "working" | "done";

export default function UploadPage() {
  const [language, setLanguage] = useState<Language>("en");
  const [file, setFile] = useState<File | null>(null);
  const [title, setTitle] = useState("");
  const [author, setAuthor] = useState("");
  const [tradition, setTradition] = useState("");
  const [era, setEra] = useState("");
  const [traditions, setTraditions] = useState<string[]>([]);
  const [phase, setPhase] = useState<Phase>("form");
  const [candidate, setCandidate] = useState<Persona | null>(null);
  const [result, setResult] = useState<UploadResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const s = strings(language);

  useEffect(() => {
    api
      .listWorks()
      .then((works) =>
        setTraditions([...new Set(works.map((w) => w.tradition))].sort()),
      )
      .catch(() => {});
  }, []);

  const submit = async (confirmId?: string) => {
    if (!file || !title.trim() || !author.trim()) {
      setError(s.uploadMissing);
      return;
    }
    setPhase("working");
    setError(null);
    const form = new FormData();
    form.set("file", file);
    form.set("title", title.trim());
    form.set("author", author.trim());
    if (tradition.trim()) form.set("tradition", tradition.trim());
    if (era.trim()) form.set("era", era.trim());
    if (confirmId !== undefined) form.set("confirm_persona_id", confirmId);
    try {
      const res = await api.uploadWork(form);
      setResult(res);
      setCandidate(null);
      setPhase("done");
    } catch (e) {
      setPhase("form");
      if (e instanceof AmbiguousMatchError) {
        setCandidate(e.candidate);
      } else {
        const msg = String(e);
        setError(
          msg.includes("413")
            ? s.uploadTooBig
            : msg.includes("415")
              ? s.uploadBadType
              : `${s.uploadFailed} (${msg})`,
        );
      }
    }
  };

  const inputClass =
    "mt-1 w-full rounded-lg border border-stone-800 bg-stone-900 px-3 py-2 text-sm text-stone-100 placeholder:text-stone-600 focus:border-amber-700 focus:outline-none";

  return (
    <div className="mx-auto min-h-screen max-w-xl px-6 py-10">
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

      <h1 className="mt-6 font-serif text-3xl font-semibold text-stone-100">
        {s.uploadHeading}
      </h1>

      {phase === "done" && result ? (
        <div className="mt-6 rounded-xl border border-emerald-800/60 bg-emerald-950/30 p-5">
          <p className="text-sm text-stone-200">{s.uploadSuccess(result.work.title)}</p>
          <p className="mt-1 text-xs text-stone-500">
            {result.work.author} · {s.passages(result.work.chunks)}
          </p>
          {result.persona_status === "created" && (
            <p className="mt-2 text-xs text-emerald-400">{s.personaForged}</p>
          )}
          {result.persona_status === "failed" && (
            <p className="mt-2 text-xs text-amber-400">{s.personaForgeFailed}</p>
          )}
          <div className="mt-4 flex gap-4 text-sm">
            <Link
              href={`/read/${result.work.id}`}
              className="text-stone-400 transition hover:text-amber-300"
            >
              {s.readWork} →
            </Link>
            {result.persona_id && (
              <Link
                href={`/personas/${result.persona_id}`}
                className="text-stone-400 transition hover:text-amber-300"
              >
                {s.startConversation}
              </Link>
            )}
          </div>
        </div>
      ) : (
        <form
          className="mt-6 space-y-4"
          onSubmit={(e) => {
            e.preventDefault();
            void submit();
          }}
        >
          <label className="block text-sm text-stone-400">
            {s.uploadFile}
            <input
              type="file"
              accept=".txt,.md,.pdf,.epub"
              onChange={(e) => setFile(e.target.files?.[0] ?? null)}
              className="mt-1 block w-full text-sm text-stone-400 file:mr-3 file:rounded-lg file:border-0 file:bg-stone-800 file:px-3 file:py-1.5 file:text-sm file:text-stone-200 hover:file:bg-stone-700"
            />
          </label>
          <label className="block text-sm text-stone-400">
            {s.uploadWorkTitle} *
            <input
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              className={inputClass}
            />
          </label>
          <label className="block text-sm text-stone-400">
            {s.uploadAuthor} *
            <input
              value={author}
              onChange={(e) => setAuthor(e.target.value)}
              className={inputClass}
            />
          </label>
          <div className="grid grid-cols-2 gap-4">
            <label className="block text-sm text-stone-400">
              {s.uploadTradition}
              <input
                value={tradition}
                onChange={(e) => setTradition(e.target.value)}
                list="traditions"
                className={inputClass}
              />
              <datalist id="traditions">
                {traditions.map((t) => (
                  <option key={t} value={t} />
                ))}
              </datalist>
            </label>
            <label className="block text-sm text-stone-400">
              {s.uploadEra}
              <input
                value={era}
                onChange={(e) => setEra(e.target.value)}
                className={inputClass}
              />
            </label>
          </div>

          {candidate && (
            <div className="rounded-xl border border-amber-800/60 bg-amber-950/30 p-4">
              <p className="text-sm text-stone-200">{s.confirmMatch(candidate.name)}</p>
              <div className="mt-3 flex flex-wrap gap-3">
                <button
                  type="button"
                  onClick={() => void submit(candidate.id)}
                  className="rounded-lg bg-amber-700/80 px-3 py-1.5 text-sm text-stone-100 transition hover:bg-amber-600"
                >
                  {s.useExisting}
                </button>
                <button
                  type="button"
                  onClick={() => void submit("decline")}
                  className="rounded-lg border border-stone-700 px-3 py-1.5 text-sm text-stone-300 transition hover:border-stone-500"
                >
                  {s.createSeparate}
                </button>
              </div>
            </div>
          )}

          {error && <p className="text-sm text-rose-400">{error}</p>}
          {phase === "working" && <p className="text-sm text-stone-500">{s.uploading}</p>}

          <button
            type="submit"
            disabled={phase === "working"}
            className="rounded-lg bg-amber-700/80 px-4 py-2 text-sm font-medium text-stone-100 transition hover:bg-amber-600 disabled:opacity-50"
          >
            {s.uploadSubmit}
          </button>
        </form>
      )}
    </div>
  );
}
