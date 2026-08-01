import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import type { Persona } from "@/lib/types";

import PersonaPicker from "./PersonaPicker";

const PERSONAS: Persona[] = [
  {
    id: "socrates",
    name: "Socrates",
    era: "Classical Greece",
    tradition: "Greek",
    color: "amber",
    greeting: "Know thyself.",
  },
  {
    id: "nietzsche",
    name: "Nietzsche",
    era: "19th century",
    tradition: "German",
    color: "rose",
    greeting: "Become who you are.",
  },
  {
    id: "freud",
    name: "Freud",
    era: "20th century",
    tradition: "Austrian",
    color: "violet",
    greeting: "Dreams are the royal road.",
  },
];

function setup(overrides: Partial<Parameters<typeof PersonaPicker>[0]> = {}) {
  const props = {
    personas: PERSONAS,
    mode: "discuss" as const,
    language: "en" as const,
    selected: ["socrates"],
    maxPersonas: 2,
    locked: false,
    onModeChange: vi.fn(),
    onLanguageChange: vi.fn(),
    onToggle: vi.fn(),
    ...overrides,
  };
  render(<PersonaPicker {...props} />);
  return props;
}

describe("PersonaPicker", () => {
  it("shows the selection count and toggles a persona on click", () => {
    const { onToggle } = setup();
    expect(screen.getByText(/Choose up to 2 thinkers \(1\/2\)/)).toBeTruthy();
    fireEvent.click(screen.getByText("Nietzsche"));
    expect(onToggle).toHaveBeenCalledWith("nietzsche");
  });

  it("disables unselected personas once the cap is reached", () => {
    setup({ selected: ["socrates", "nietzsche"] });
    const freud = screen.getByText("Freud").closest("button")!;
    expect(freud.disabled).toBe(true);
    // Selected personas stay enabled so they can be deselected.
    const socrates = screen.getByText("Socrates").closest("button")!;
    expect(socrates.disabled).toBe(false);
  });

  it("disables everything when locked", () => {
    setup({ locked: true });
    const socrates = screen.getByText("Socrates").closest("button")!;
    expect(socrates.disabled).toBe(true);
    expect(screen.getByRole("button", { name: "study" })).toHaveProperty(
      "disabled",
      true,
    );
  });

  it("switches to study mode and shows the Tutor", () => {
    const { onModeChange } = setup({ mode: "study" });
    expect(screen.getByText("The Tutor")).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "discuss" }));
    expect(onModeChange).toHaveBeenCalledWith("discuss");
  });

  it("switches language and localizes the mode labels", () => {
    const { onLanguageChange } = setup({ language: "zh" });
    expect(screen.getByRole("button", { name: "对话" })).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "中文" }));
    // Already zh — clicking again still reports the choice.
    expect(onLanguageChange).toHaveBeenCalledWith("zh");
  });

  it("locks the language switch when locked", () => {
    setup({ locked: true });
    expect(screen.getByRole("button", { name: "中文" })).toHaveProperty(
      "disabled",
      true,
    );
  });
});
