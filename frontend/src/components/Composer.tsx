"use client";

import { useEffect, useRef, useState } from "react";
import { strings } from "@/lib/i18n";
import type { Language } from "@/lib/types";

interface Props {
  disabled: boolean;
  placeholder: string;
  language?: Language;
  onSend: (text: string) => void;
  /** External text injection (e.g. a quoted passage); applied once per nonce. */
  prefill?: { text: string; nonce: number } | null;
}

export default function Composer({
  disabled,
  placeholder,
  language = "en",
  onSend,
  prefill = null,
}: Props) {
  const [text, setText] = useState("");
  const appliedNonceRef = useRef(0);
  const s = strings(language);

  useEffect(() => {
    if (prefill && prefill.nonce !== appliedNonceRef.current) {
      appliedNonceRef.current = prefill.nonce;
      setText((prev) => prefill.text + prev);
    }
  }, [prefill]);

  const submit = () => {
    const trimmed = text.trim();
    if (!trimmed || disabled) return;
    onSend(trimmed);
    setText("");
  };

  return (
    <div className="border-t border-stone-800 bg-stone-900/50 px-6 py-4">
      <div className="mx-auto flex max-w-3xl items-end gap-3">
        <textarea
          value={text}
          rows={2}
          onChange={(e) => setText(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter" && !e.shiftKey) {
              e.preventDefault();
              submit();
            }
          }}
          placeholder={placeholder}
          className="flex-1 resize-none rounded-xl border border-stone-700 bg-stone-900 px-4 py-3 text-stone-100 placeholder-stone-600 outline-none transition focus:border-amber-700/70"
        />
        <button
          onClick={submit}
          disabled={disabled || !text.trim()}
          className="rounded-xl border border-amber-700/50 bg-amber-500/15 px-4 py-3 text-sm font-medium text-amber-200 transition hover:bg-amber-500/25 disabled:cursor-not-allowed disabled:opacity-40"
        >
          {disabled ? s.thinking : s.send}
        </button>
      </div>
      <p className="mx-auto mt-2 max-w-3xl text-xs text-stone-600">{s.composerHint}</p>
    </div>
  );
}
