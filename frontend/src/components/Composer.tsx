"use client";

import { useState } from "react";

interface Props {
  disabled: boolean;
  placeholder: string;
  onSend: (text: string) => void;
}

export default function Composer({ disabled, placeholder, onSend }: Props) {
  const [text, setText] = useState("");

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
          {disabled ? "Thinking…" : "Send"}
        </button>
      </div>
      <p className="mx-auto mt-2 max-w-3xl text-xs text-stone-600">
        Enter to send · Shift+Enter for a new line · Personas speak from retrieved
        passages, but they are still interpretations.
      </p>
    </div>
  );
}
