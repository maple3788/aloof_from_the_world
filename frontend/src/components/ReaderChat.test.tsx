import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import type { Persona, Session } from "@/lib/types";

import ReaderChat from "./ReaderChat";

vi.mock("@/lib/api", () => ({
  api: {
    listPersonas: vi.fn(),
    generatePersona: vi.fn(),
    createSession: vi.fn(),
  },
  streamChat: vi.fn(),
}));

import { api, streamChat } from "@/lib/api";

const PLATO: Persona = {
  id: "plato",
  name: "Plato",
  era: "Classical Greece",
  tradition: "Western philosophy",
  color: "sky",
  greeting: "Come, friend — shall we turn toward the light?",
  greeting_zh: "来吧，朋友。",
};

const MARCUS: Persona = {
  id: "marcus_aurelius",
  name: "Marcus Aurelius",
  era: "Roman Empire",
  tradition: "Stoicism",
  color: "violet",
  greeting: "Waste no more time arguing what a good man should be. Be one.",
  greeting_zh: "别再空谈，去做一个好人。",
};

const SESSION: Session = {
  id: "s1",
  title: "Reading The Republic",
  mode: "discuss",
  language: "en",
  persona_ids: ["plato"],
  work_id: "plato_republic",
  created_at: "2026-08-01T01:00:00Z",
};

beforeEach(() => {
  vi.clearAllMocks();
});

describe("ReaderChat", () => {
  it("resolves the matched persona and chats scoped to the work", async () => {
    vi.mocked(api.listPersonas).mockResolvedValue([PLATO]);
    vi.mocked(api.createSession).mockResolvedValue(SESSION);
    vi.mocked(streamChat).mockImplementation(async (_sid, _message, onEvent) => {
      onEvent({ type: "token", persona: "plato", content: "The cave, friend — " });
      onEvent({
        type: "done",
        responses: [
          {
            responder: "plato",
            responder_name: "Plato",
            content: "The cave, friend — shadows deceive.",
            citations: [],
            critic_note: null,
          },
        ],
      });
    });

    render(
      <ReaderChat
        workId="plato_republic"
        author="Plato"
        personaId="plato"
        language="en"
        prefill={null}
      />,
    );

    expect(await screen.findByText(/Come, friend/)).toBeDefined();
    const composer = screen.getByPlaceholderText("Ask Plato about the text…");
    fireEvent.change(composer, { target: { value: "What is the cave?" } });
    fireEvent.keyDown(composer, { key: "Enter" });

    await waitFor(() => {
      expect(api.createSession).toHaveBeenCalledWith(
        "discuss",
        ["plato"],
        "en",
        "plato_republic",
      );
    });
    expect(
      await screen.findByText("The cave, friend — shadows deceive."),
    ).toBeDefined();
  });

  it("summons a forged persona when none matches the author", async () => {
    vi.mocked(api.generatePersona).mockResolvedValue(MARCUS);
    render(
      <ReaderChat
        workId="marcus_meditations"
        author="Marcus Aurelius"
        personaId={null}
        language="en"
        prefill={null}
      />,
    );

    expect(screen.getByText("Summoning Marcus Aurelius…")).toBeDefined();
    expect(await screen.findByText(/Waste no more time/)).toBeDefined();
    expect(api.generatePersona).toHaveBeenCalledWith("marcus_meditations");
  });

  it("falls back to reading-only with retry when summoning fails", async () => {
    vi.mocked(api.generatePersona).mockRejectedValue(new Error("502"));
    render(
      <ReaderChat
        workId="marcus_meditations"
        author="Marcus Aurelius"
        personaId={null}
        language="en"
        prefill={null}
      />,
    );

    expect(
      await screen.findByText("Could not summon the author — reading only."),
    ).toBeDefined();
    expect(screen.queryByPlaceholderText(/about the text/)).toBeNull();

    vi.mocked(api.generatePersona).mockResolvedValue(MARCUS);
    fireEvent.click(screen.getByRole("button", { name: "Try again" }));
    expect(await screen.findByText(/Waste no more time/)).toBeDefined();
  });
});
