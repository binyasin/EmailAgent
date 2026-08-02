import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { api } from "../api/client";
import ApprovalInbox from "./ApprovalInbox";

vi.mock("../api/client", () => ({
  api: {
    listDrafts: vi.fn(),
    approveDraft: vi.fn(),
    rejectDraft: vi.fn(),
  },
}));

const sampleDraft = {
  id: "draft-1",
  mailbox_connection_id: "mb-1",
  provider_draft_id: "gmail-draft-1",
  thread_id: "thread-1",
  subject: "Re: Project update",
  snippet: "Thanks for the update, here's my reply...",
  status: "pending_review",
  created_by_skill: "draft-reply",
  created_at: new Date().toISOString(),
};

describe("ApprovalInbox", () => {
  beforeEach(() => {
    vi.mocked(api.listDrafts).mockResolvedValue([sampleDraft]);
    vi.mocked(api.approveDraft).mockResolvedValue({ ...sampleDraft, status: "sent" });
    vi.mocked(api.rejectDraft).mockResolvedValue({ ...sampleDraft, status: "rejected" });
  });

  it("renders pending drafts", async () => {
    render(<ApprovalInbox />);
    expect(await screen.findByText("Re: Project update")).toBeInTheDocument();
    expect(screen.getByTestId("draft-card")).toBeInTheDocument();
  });

  it("removes a draft from the list after approval", async () => {
    render(<ApprovalInbox />);
    await screen.findByText("Re: Project update");

    await userEvent.click(screen.getByRole("button", { name: /approve/i }));

    await waitFor(() => expect(api.approveDraft).toHaveBeenCalledWith("draft-1"));
    await waitFor(() => expect(screen.queryByText("Re: Project update")).not.toBeInTheDocument());
  });

  it("rolls back the optimistic removal if approval fails", async () => {
    vi.mocked(api.approveDraft).mockRejectedValue(new Error("send failed"));
    render(<ApprovalInbox />);
    await screen.findByText("Re: Project update");

    await userEvent.click(screen.getByRole("button", { name: /approve/i }));

    await waitFor(() => expect(screen.getByText("Re: Project update")).toBeInTheDocument());
    expect(await screen.findByText(/send failed/i)).toBeInTheDocument();
  });
});
