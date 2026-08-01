"use client";

import { useMemo, useState } from "react";
import { strings } from "@/lib/i18n";
import type { Language } from "@/lib/types";

export const MAX_QUOTE_CHARS = 2000;

interface Props {
  title: string;
  author: string;
  text: string;
  language?: Language;
  onAskSelection: (quote: string) => void;
}

export default function ReaderPane({
  title,
  author,
  text,
  language = "en",
  onAskSelection,
}: Props) {
  const [selection, setSelection] = useState("");
  const s = strings(language);
  const paragraphs = useMemo(() => text.split(/\n{2,}/), [text]);
  const tooLong = selection.length > MAX_QUOTE_CHARS;

  const capture = () => {
    setSelection(window.getSelection()?.toString().trim() ?? "");
  };

  const ask = () => {
    onAskSelection(selection);
    setSelection("");
    window.getSelection()?.removeAllRanges();
  };

  return (
    <div className="relative flex min-h-0 flex-1 flex-col">
      <header className="shrink-0 border-b border-stone-800 px-6 py-3">
        <h2 className="font-serif text-xl font-semibold text-stone-100">{title}</h2>
        <p className="mt-0.5 text-xs text-stone-500">{author}</p>
      </header>

      <div className="flex-1 overflow-y-auto px-6 py-6 scrollbar-thin" onMouseUp={capture}>
        <div className="mx-auto max-w-prose space-y-4 font-serif leading-relaxed text-stone-300">
          {paragraphs.map((p, i) => (
            <p key={i} className="whitespace-pre-wrap">
              {p}
            </p>
          ))}
        </div>
      </div>

      {selection && (
        <div className="absolute bottom-4 left-1/2 -translate-x-1/2">
          {tooLong ? (
            <span className="rounded-full border border-stone-700 bg-stone-900 px-4 py-2 text-xs text-stone-500 shadow-lg">
              {s.selectionTooLong}
            </span>
          ) : (
            <button
              onClick={ask}
              className="rounded-full border border-amber-700/60 bg-amber-500/15 px-4 py-2 text-sm font-medium text-amber-200 shadow-lg transition hover:bg-amber-500/25"
            >
              {s.askAboutSelection}
            </button>
          )}
        </div>
      )}
    </div>
  );
}
