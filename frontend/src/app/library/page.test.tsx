import { render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import type { Persona, Work } from "@/lib/types";

vi.mock("@/lib/api", () => ({
  api: {
    listPersonas: vi.fn(),
    listWorks: vi.fn(),
  },
}));

import { api } from "@/lib/api";

import LibraryPage from "./page";

const PLATO: Persona = {
  id: "plato",
  name: "Plato",
  era: "Classical Greece",
  tradition: "Western philosophy",
  color: "sky",
  greeting: "Come, friend.",
};

const REPUBLIC: Work = {
  id: "plato_republic",
  title: "The Republic",
  author: "Plato",
  tradition: "Western philosophy",
  era: "Classical Greece",
  gutenberg_id: 1497,
  chunks: 1014,
  persona_id: "plato",
};

const HISTORIES: Work = {
  id: "thucydides_history",
  title: "History of the Peloponnesian War",
  author: "Thucydides",
  tradition: "Historiography",
  era: "Classical Greece",
  gutenberg_id: 7142,
  chunks: 0,
  persona_id: null,
};

beforeEach(() => {
  vi.clearAllMocks();
  vi.mocked(api.listPersonas).mockResolvedValue([PLATO]);
  vi.mocked(api.listWorks).mockResolvedValue([REPUBLIC, HISTORIES]);
});

describe("LibraryPage", () => {
  it("links speaker cards to their persona detail pages", async () => {
    render(<LibraryPage />);
    // The card's accessible name includes its greeting; the corpus author
    // cell link is exactly "Plato".
    await waitFor(() => screen.getByRole("link", { name: /Come, friend\./ }));
    const card = screen.getByRole("link", { name: /Come, friend\./ });
    expect(card.getAttribute("href")).toBe("/personas/plato");
  });

  it("links the author cell only when a persona claims them", async () => {
    render(<LibraryPage />);
    await waitFor(() => screen.getByText("The Republic"));

    const authorLink = screen.getByRole("link", { name: "Plato" });
    expect(authorLink.getAttribute("href")).toBe("/personas/plato");
    // Thucydides has no persona: plain text, not a link.
    expect(screen.queryByRole("link", { name: "Thucydides" })).toBeNull();
    expect(screen.getByText("Thucydides")).toBeTruthy();
  });
});
