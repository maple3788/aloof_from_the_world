import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import type { Persona, Session, TraceDetail, TraceSummary } from "@/lib/types";

import TraceBoard from "./TraceBoard";

vi.mock("@/lib/api", () => ({
  api: { getTrace: vi.fn() },
}));

import { api } from "@/lib/api";

const SESSIONS: Session[] = [
  {
    id: "s1",
    title: "美德对话",
    mode: "discuss",
    language: "zh",
    persona_ids: ["socrates"],
    created_at: "2026-08-01T01:00:00Z",
  },
];

const PERSONAS: Persona[] = [
  {
    id: "socrates",
    name: "Socrates",
    era: "Classical Greece",
    tradition: "Greek",
    color: "amber",
    greeting: "Know thyself.",
  },
];

const TRACES: TraceSummary[] = [
  {
    id: "t1",
    session_id: "s1",
    query: "什么是美德？",
    mode: "discuss",
    language: "zh",
    speakers: ["socrates"],
    status: "ok",
    error: null,
    total_ms: 4210,
    created_at: "2026-08-01T01:00:05Z",
  },
  {
    id: "t2",
    session_id: "s1",
    query: "Exploded turn",
    mode: "discuss",
    language: "en",
    speakers: ["socrates"],
    status: "error",
    error: "graph exploded",
    total_ms: 120,
    created_at: "2026-08-01T01:01:00Z",
  },
];

const DETAIL: TraceDetail = {
  ...TRACES[0],
  detail: {
    retrieval_query: "What is virtue?",
    translation_ms: 380,
    retrievals: [
      {
        persona: "socrates",
        ms: 14,
        docs: [
          {
            work_id: "plato_apology",
            title: "Apology",
            author: "Plato",
            era: "Classical Greece",
            chunk_index: 3,
            excerpt: "The unexamined life is not worth living...",
          },
        ],
      },
    ],
    replies: [{ persona: "socrates", ms: 2350, chars: 512 }],
    critic: [
      {
        persona: "socrates",
        supported: false,
        note: "回应超出了原文直接支持的范围。",
        citations: 1,
        from_cache: false,
      },
    ],
  },
};

function setup(overrides: Partial<Parameters<typeof TraceBoard>[0]> = {}) {
  const props = {
    traces: TRACES,
    sessions: SESSIONS,
    personas: PERSONAS,
    language: "en" as const,
    ...overrides,
  };
  render(<TraceBoard {...props} />);
  return props;
}

describe("TraceBoard", () => {
  beforeEach(() => {
    vi.mocked(api.getTrace).mockReset();
  });

  it("lists traced queries with badges, session title, and speaker chips", () => {
    setup();
    expect(screen.getByText("什么是美德？")).toBeTruthy();
    expect(screen.getByText("Exploded turn")).toBeTruthy();
    expect(screen.getAllByText("美德对话").length).toBeGreaterThan(0);
    expect(screen.getAllByText("中文").length).toBeGreaterThan(0);
    expect(screen.getAllByText("Socrates").length).toBeGreaterThan(0);
    expect(screen.getByText("4.2s")).toBeTruthy();
  });

  it("shows the empty state when there are no traces", () => {
    setup({ traces: [] });
    expect(screen.getByText(/No traces yet/)).toBeTruthy();
  });

  it("expands a row to show retrieval, reply, and critic detail", async () => {
    vi.mocked(api.getTrace).mockResolvedValue(DETAIL);
    setup();
    fireEvent.click(screen.getByText("什么是美德？"));
    await waitFor(() => expect(api.getTrace).toHaveBeenCalledWith("t1"));
    await screen.findByText("Apology");
    expect(screen.getByText(/What is virtue\?/)).toBeTruthy();
    expect(screen.getByText(/回应超出了原文直接支持的范围。/)).toBeTruthy();
    expect(screen.getByText(/2350 ms/)).toBeTruthy();
  });

  it("collapses an expanded row on second click without refetching", async () => {
    vi.mocked(api.getTrace).mockResolvedValue(DETAIL);
    setup();
    fireEvent.click(screen.getByText("什么是美德？"));
    await screen.findByText("Apology");
    fireEvent.click(screen.getByText("什么是美德？"));
    expect(screen.queryByText("Apology")).toBeNull();
    fireEvent.click(screen.getByText("什么是美德？"));
    await screen.findByText("Apology");
    expect(api.getTrace).toHaveBeenCalledTimes(1);
  });

  it("renders localized labels in Chinese", () => {
    setup({ language: "zh", traces: [] });
    expect(screen.getByText(/暂无追踪记录/)).toBeTruthy();
  });
});
