import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { api } from "../api/client";
import SkillSettings from "./SkillSettings";

vi.mock("../api/client", async () => {
  const actual = await vi.importActual<typeof import("../api/client")>("../api/client");
  return {
    ...actual,
    api: {
      listSkillSettings: vi.fn(),
      listVipRules: vi.fn(),
      updateSkillSetting: vi.fn(),
      createVipRule: vi.fn(),
      deleteVipRule: vi.fn(),
    },
  };
});

describe("SkillSettings", () => {
  beforeEach(() => {
    vi.mocked(api.listSkillSettings).mockResolvedValue([]);
    vi.mocked(api.listVipRules).mockResolvedValue([]);
  });

  it("shows triage/draft-reply enabled by default when unconfigured", async () => {
    render(<SkillSettings />);
    const triageCheckbox = await screen.findByLabelText("triage");
    expect(triageCheckbox).toBeChecked();

    const digestCheckbox = screen.getByLabelText("digest");
    expect(digestCheckbox).not.toBeChecked();
  });

  it("toggles a skill on click", async () => {
    vi.mocked(api.updateSkillSetting).mockResolvedValue({
      id: "s1",
      skill_name: "digest",
      enabled: true,
      params: {},
      created_at: new Date().toISOString(),
    });

    render(<SkillSettings />);
    const digestCheckbox = await screen.findByLabelText("digest");
    await userEvent.click(digestCheckbox);

    await waitFor(() => expect(api.updateSkillSetting).toHaveBeenCalledWith("digest", true));
  });

  it("adds a VIP rule", async () => {
    vi.mocked(api.createVipRule).mockResolvedValue({
      id: "v1",
      sender_pattern: "ceo@example.com",
      priority: 0,
      created_at: new Date().toISOString(),
    });

    render(<SkillSettings />);
    await screen.findByLabelText("triage");

    const input = screen.getByPlaceholderText(/ceo@example.com/i);
    await userEvent.type(input, "ceo@example.com");
    await userEvent.click(screen.getByRole("button", { name: /add/i }));

    await waitFor(() => expect(api.createVipRule).toHaveBeenCalledWith("ceo@example.com"));
    expect(await screen.findByText("ceo@example.com")).toBeInTheDocument();
  });
});
