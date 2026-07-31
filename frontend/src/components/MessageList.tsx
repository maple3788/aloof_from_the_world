"use client";

import { useEffect, useRef, useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { personaTheme } from "@/lib/colors";
import type { Citation, Message, Persona } from "@/lib/types";

interface Props {
  messages: Message[];
  personas: Persona[];
}

function personaName(personas: Persona[], id?: string | null): string {
  if (!id) return "Assistant";
  if (id === "tutor") return "Tutor";
  return personas.find((p) => p.id === id)?.name ?? id;
}

function personaColor(personas: Persona[], id?: string | null): string | undefined {
  return personas.find((p) => p.id === id)?.color;
}

function CitationChip({ citation, index }: { citation: Citation; index: number }) {
  const [open, setOpen] = useState(false);
  return (
    <span className="inline-block">
      <button
        onClick={() => setOpen((v) => !v)}
        className="rounded-full border border-stone-700 bg-stone-800/60 px-2.5 py-0.5 text-xs text-stone-400 transition hover:border-amber-700/60 hover:text-amber-300"
        title={citation.title}
      >
        [{index + 1}] {citation.title} — {citation.author}
      </button>
      {open && (
        <span className="mt-1 block rounded-lg border border-stone-800 bg-stone-900 p-3 text-xs leading-relaxed text-stone-400">
          <span className="mb-1 block text-stone-500">
            {citation.era} · chunk {citation.chunk_index}
          </span>
          “{citation.excerpt}”
        </span>
      )}
    </span>
  );
}

export default function MessageList({ messages, personas }: Props) {
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  return (
    <div className="flex-1 space-y-6 overflow-y-auto px-6 py-6 scrollbar-thin">
      {messages.map((msg, i) => {
        if (msg.role === "user") {
          return (
            <div key={i} className="flex justify-end">
              <div className="max-w-[75%] rounded-2xl rounded-br-sm border border-stone-700 bg-stone-800 px-4 py-2.5 text-stone-100">
                {msg.content}
              </div>
            </div>
          );
        }

        const theme = personaTheme(msg.persona_id ?? "", personaColor(personas, msg.persona_id));
        return (
          <div key={i} className="flex justify-start">
            <div className="max-w-[85%] space-y-2">
              <span
                className={`inline-flex items-center gap-1.5 rounded-full border px-2.5 py-0.5 text-xs font-medium ${theme.chip}`}
              >
                <span className={`h-1.5 w-1.5 rounded-full ${theme.dot}`} />
                {personaName(personas, msg.persona_id)}
              </span>
              <div className="prose-chat rounded-2xl rounded-tl-sm border border-stone-800 bg-stone-900/70 px-4 py-3 text-stone-200">
                <ReactMarkdown remarkPlugins={[remarkGfm]}>
                  {msg.content}
                </ReactMarkdown>
                {msg.streaming && (
                  <span className="ml-1 inline-block h-4 w-1.5 animate-pulse bg-amber-500/70" />
                )}
              </div>
              {msg.critic_note && (
                <p className="text-xs italic text-stone-500">
                  Moderator&apos;s note: {msg.critic_note}
                </p>
              )}
              {msg.citations && msg.citations.length > 0 && (
                <div className="flex flex-wrap gap-1.5">
                  {msg.citations.map((c, j) => (
                    <CitationChip key={j} citation={c} index={j} />
                  ))}
                </div>
              )}
            </div>
          </div>
        );
      })}
      <div ref={bottomRef} />
    </div>
  );
}
