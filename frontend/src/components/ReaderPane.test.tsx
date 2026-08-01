import { fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import ReaderPane, { MAX_QUOTE_CHARS } from "./ReaderPane";

function mockSelection(text: string) {
  vi.spyOn(window, "getSelection").mockReturnValue({
    toString: () => text,
    removeAllRanges: vi.fn(),
  } as unknown as Selection);
}

afterEach(() => {
  vi.restoreAllMocks();
});

describe("ReaderPane", () => {
  it("renders paragraphs split on blank lines", () => {
    render(
      <ReaderPane
        title="The Republic"
        author="Plato"
        text={"First paragraph.\n\nSecond paragraph."}
        onAskSelection={vi.fn()}
      />,
    );
    expect(screen.getByText("First paragraph.")).toBeDefined();
    expect(screen.getByText("Second paragraph.")).toBeDefined();
  });

  it("shows the ask button on selection and forwards the quote", () => {
    const onAskSelection = vi.fn();
    mockSelection("justice is the advantage of the stronger");
    render(
      <ReaderPane
        title="The Republic"
        author="Plato"
        text="body"
        onAskSelection={onAskSelection}
      />,
    );
    fireEvent.mouseUp(screen.getByText("body"));
    fireEvent.click(screen.getByRole("button", { name: "Ask about selection" }));
    expect(onAskSelection).toHaveBeenCalledWith(
      "justice is the advantage of the stronger",
    );
    expect(screen.queryByRole("button", { name: "Ask about selection" })).toBeNull();
  });

  it("shows a too-long hint instead of the button for oversized selections", () => {
    mockSelection("x".repeat(MAX_QUOTE_CHARS + 1));
    render(
      <ReaderPane title="The Republic" author="Plato" text="body" onAskSelection={vi.fn()} />,
    );
    fireEvent.mouseUp(screen.getByText("body"));
    expect(screen.queryByRole("button", { name: "Ask about selection" })).toBeNull();
    expect(screen.getByText(/too long/i)).toBeDefined();
  });

  it("shows nothing when there is no selection", () => {
    mockSelection("");
    render(
      <ReaderPane title="The Republic" author="Plato" text="body" onAskSelection={vi.fn()} />,
    );
    fireEvent.mouseUp(screen.getByText("body"));
    expect(screen.queryByRole("button", { name: "Ask about selection" })).toBeNull();
  });
});
