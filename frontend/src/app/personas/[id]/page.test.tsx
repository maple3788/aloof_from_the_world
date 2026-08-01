import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import type { PersonaDetail } from "@/lib/types";

vi.mock("next/navigation", () => ({
  useParams: () => ({ id: "plato" }),
}));

vi.mock("@/lib/api", () => ({
  api: {
    getPersona: vi.fn(),
  },
}));

import { api } from "@/lib/api";

import PersonaPage from "./page";

const PLATO: PersonaDetail = {
  id: "plato",
  name: "Plato",
  era: "Classical Greece, 428-348 BC",
  tradition: "Western philosophy",
  color: "sky",
  greeting: "Come, friend — shall we turn toward the light?",
  greeting_zh: "来吧，朋友。",
  authors: ["Plato"],
  traditions: ["Western philosophy"],
  voice: "You are Plato of Athens: builder of systems in writing.",
  worldview: "Behind appearances lies the eternal realm of Forms.",
  style_rules: ["Reason systematically.", "Illuminate with image and myth."],
  works: [
    {
      id: "plato_republic",
      title: "The Republic",
      author: "Plato",
      tradition: "Western philosophy",
      era: "Classical Greece",
      gutenberg_id: 1497,
      chunks: 1014,
      persona_id: "plato",
    },
  ],
};

beforeEach(() => {
  vi.clearAllMocks();
});

describe("PersonaPage", () => {
  it("renders the full card and links its works", async () => {
    vi.mocked(api.getPersona).mockResolvedValue(PLATO);
    render(<PersonaPage />);

    await waitFor(() => screen.getByText("Plato"));
    expect(api.getPersona).toHaveBeenCalledWith("plato");
    expect(screen.getByText(/You are Plato of Athens/)).toBeTruthy();
    expect(screen.getByText(/realm of Forms/)).toBeTruthy();
    expect(screen.getByText("Reason systematically.")).toBeTruthy();
    // toLocaleString grouping varies with the test env's ICU build.
    expect(screen.getByText(/1,?014 passages/)).toBeTruthy();

    const readLink = screen.getByRole("link", { name: "Read →" });
    expect(readLink.getAttribute("href")).toBe("/read/plato_republic");

    const chatLink = screen.getByRole("link", { name: "Start a conversation →" });
    expect(chatLink.getAttribute("href")).toBe("/?personas=plato");
  });

  it("switches the greeting to Chinese on the language toggle", async () => {
    vi.mocked(api.getPersona).mockResolvedValue(PLATO);
    render(<PersonaPage />);

    await waitFor(() => screen.getByText(/Come, friend/));
    fireEvent.click(screen.getByRole("button", { name: "中文" }));
    expect(screen.getByText(/来吧，朋友。/)).toBeTruthy();
    expect(screen.getByText("世界观")).toBeTruthy();
  });

  it("shows a not-found message when the fetch fails", async () => {
    vi.mocked(api.getPersona).mockRejectedValue(new Error("404"));
    render(<PersonaPage />);

    await waitFor(() => screen.getByText(/Persona not found/));
  });
});
