import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import type { Persona, UploadResult } from "@/lib/types";

vi.mock("@/lib/api", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@/lib/api")>();
  return {
    ...actual,
    api: {
      listWorks: vi.fn().mockResolvedValue([]),
      uploadWork: vi.fn(),
    },
  };
});

import { AmbiguousMatchError, api } from "@/lib/api";

import UploadPage from "./page";

const MARCUS: Persona = {
  id: "marcus_aurelius",
  name: "Marcus Aurelius",
  era: "Roman Empire",
  tradition: "Stoicism",
  color: "violet",
  greeting: "Waste no more time.",
};

const RESULT: UploadResult = {
  work: {
    id: "upload_letter_i_abc123",
    title: "Letter I",
    author: "Seneca",
    tradition: "Stoicism",
    era: "Roman Empire",
    chunks: 12,
    persona_id: null,
    source: "upload",
  },
  persona_id: null,
  match: "none",
};

function fillForm() {
  fireEvent.change(screen.getByLabelText(/File \(/), {
    target: { files: [new File(["some text"], "seneca.txt")] },
  });
  fireEvent.change(screen.getByLabelText(/Title/), { target: { value: "Letter I" } });
  fireEvent.change(screen.getByLabelText(/Author/), { target: { value: "Seneca" } });
}

beforeEach(() => {
  vi.clearAllMocks();
  vi.mocked(api.listWorks).mockResolvedValue([]);
});

describe("UploadPage", () => {
  it("requires a file, title, and author before submitting", async () => {
    render(<UploadPage />);
    fireEvent.click(screen.getByRole("button", { name: "Upload and index" }));
    expect(await screen.findByText(/Choose a file/)).toBeTruthy();
    expect(api.uploadWork).not.toHaveBeenCalled();
  });

  it("shows the success panel with a read link after upload", async () => {
    vi.mocked(api.uploadWork).mockResolvedValue(RESULT);
    render(<UploadPage />);
    fillForm();
    fireEvent.click(screen.getByRole("button", { name: "Upload and index" }));

    await waitFor(() => screen.getByText(/Added “Letter I” to the library/));
    const readLink = screen.getByRole("link", { name: "Read →" });
    expect(readLink.getAttribute("href")).toBe("/read/upload_letter_i_abc123");
  });

  it("asks for confirmation on an ambiguous author and resubmits", async () => {
    vi.mocked(api.uploadWork)
      .mockRejectedValueOnce(new AmbiguousMatchError(MARCUS))
      .mockResolvedValueOnce({ ...RESULT, persona_id: "marcus_aurelius", match: "confirmed" });
    render(<UploadPage />);
    fillForm();
    fireEvent.change(screen.getByLabelText(/Author/), {
      target: { value: "marcus aurelius" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Upload and index" }));

    await waitFor(() => screen.getByText(/close to Marcus Aurelius/));
    fireEvent.click(screen.getByRole("button", { name: "Yes, attach to this persona" }));

    await waitFor(() => screen.getByText(/Added “Letter I” to the library/));
    expect(api.uploadWork).toHaveBeenCalledTimes(2);
    const secondForm = vi.mocked(api.uploadWork).mock.calls[1][0];
    expect(secondForm.get("confirm_persona_id")).toBe("marcus_aurelius");
  });

  it("sends the decline sentinel when the user keeps the author separate", async () => {
    vi.mocked(api.uploadWork)
      .mockRejectedValueOnce(new AmbiguousMatchError(MARCUS))
      .mockResolvedValueOnce(RESULT);
    render(<UploadPage />);
    fillForm();
    fireEvent.click(screen.getByRole("button", { name: "Upload and index" }));

    await waitFor(() => screen.getByText(/close to Marcus Aurelius/));
    fireEvent.click(screen.getByRole("button", { name: "No, keep separate" }));

    await waitFor(() => screen.getByText(/Added “Letter I”/));
    const secondForm = vi.mocked(api.uploadWork).mock.calls[1][0];
    expect(secondForm.get("confirm_persona_id")).toBe("decline");
  });

  it("notes when a new persona was forged for the author", async () => {
    vi.mocked(api.uploadWork).mockResolvedValue({
      ...RESULT,
      persona_id: "seneca",
      persona_status: "created",
    });
    render(<UploadPage />);
    fillForm();
    fireEvent.click(screen.getByRole("button", { name: "Upload and index" }));

    expect(
      await screen.findByText("A new persona was forged for this author."),
    ).toBeTruthy();
    const personaLink = screen.getByRole("link", { name: "Start a conversation →" });
    expect(personaLink.getAttribute("href")).toBe("/personas/seneca");
  });

  it("notes when persona forging failed but the work is readable", async () => {
    vi.mocked(api.uploadWork).mockResolvedValue({
      ...RESULT,
      persona_status: "failed",
    });
    render(<UploadPage />);
    fillForm();
    fireEvent.click(screen.getByRole("button", { name: "Upload and index" }));

    expect(await screen.findByText(/Persona forging failed/)).toBeTruthy();
    expect(screen.getByRole("link", { name: "Read →" })).toBeTruthy();
  });

  it("maps a 413 to the too-large message", async () => {
    vi.mocked(api.uploadWork).mockRejectedValue(
      new Error("POST /library/uploads failed: 413"),
    );
    render(<UploadPage />);
    fillForm();
    fireEvent.click(screen.getByRole("button", { name: "Upload and index" }));

    expect(await screen.findByText("File too large.")).toBeTruthy();
  });
});
