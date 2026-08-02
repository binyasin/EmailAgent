import { render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { api } from "../api/client";
import DigestView from "./DigestView";

vi.mock("../api/client", () => ({
  api: { listDigests: vi.fn() },
}));

describe("DigestView", () => {
  beforeEach(() => {
    vi.mocked(api.listDigests).mockResolvedValue([
      {
        id: "digest-1",
        period: "daily",
        summary_text: "Needs attention:\n- Alice: contract renewal",
        created_at: new Date().toISOString(),
      },
    ]);
  });

  it("renders digest summaries", async () => {
    render(<DigestView />);
    expect(await screen.findByText("daily")).toBeInTheDocument();
    expect(screen.getByText(/contract renewal/)).toBeInTheDocument();
  });

  it("shows an empty state with no digests", async () => {
    vi.mocked(api.listDigests).mockResolvedValue([]);
    render(<DigestView />);
    expect(await screen.findByText(/no digests generated yet/i)).toBeInTheDocument();
  });
});
