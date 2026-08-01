import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import Composer from "./Composer";

function setup(overrides: Partial<Parameters<typeof Composer>[0]> = {}) {
  const props = {
    disabled: false,
    placeholder: "Ask your question…",
    onSend: vi.fn(),
    ...overrides,
  };
  render(<Composer {...props} />);
  return props;
}

describe("Composer", () => {
  it("sends the trimmed message and clears the textarea", () => {
    const { onSend } = setup();
    const textarea = screen.getByPlaceholderText("Ask your question…");
    fireEvent.change(textarea, { target: { value: "  What is virtue?  " } });
    fireEvent.click(screen.getByRole("button", { name: "Send" }));
    expect(onSend).toHaveBeenCalledWith("What is virtue?");
    expect((textarea as HTMLTextAreaElement).value).toBe("");
  });

  it("submits on Enter but not on Shift+Enter", () => {
    const { onSend } = setup();
    const textarea = screen.getByPlaceholderText("Ask your question…");
    fireEvent.change(textarea, { target: { value: "first line" } });
    fireEvent.keyDown(textarea, { key: "Enter", shiftKey: true });
    expect(onSend).not.toHaveBeenCalled();
    fireEvent.keyDown(textarea, { key: "Enter" });
    expect(onSend).toHaveBeenCalledWith("first line");
  });

  it("ignores blank input", () => {
    const { onSend } = setup();
    const textarea = screen.getByPlaceholderText("Ask your question…");
    fireEvent.change(textarea, { target: { value: "   " } });
    fireEvent.keyDown(textarea, { key: "Enter" });
    expect(onSend).not.toHaveBeenCalled();
  });

  it("does not send while disabled", () => {
    const { onSend } = setup({ disabled: true });
    const button = screen.getByRole("button", { name: "Thinking…" });
    expect(button).toHaveProperty("disabled", true);
    const textarea = screen.getByPlaceholderText("Ask your question…");
    fireEvent.change(textarea, { target: { value: "hello" } });
    fireEvent.keyDown(textarea, { key: "Enter" });
    expect(onSend).not.toHaveBeenCalled();
  });
});
