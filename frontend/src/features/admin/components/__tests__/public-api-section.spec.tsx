import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { PublicApiSection } from "../public-api-section";
import { useSettingsStore } from "@/store/settings";

vi.mock("@/i18n", () => ({
  t: (key: string, params?: Record<string, string>) => {
    if (key === "frontend.public_api.example_snippet" && params) {
      return `fetch("${params.url}")`;
    }
    return key;
  },
}));

const config = {
  tenant_id: "tenant-1",
  api_key: "tpk_abc",
  allowed_origins: ["https://example.com"],
  created_at: "2026-06-27T00:00:00Z",
  updated_at: "2026-06-27T00:00:00Z",
};

describe("PublicApiSection", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    useSettingsStore.getState().clearSettingsCache();
  });

  it("loads and shows the existing key and origins", async () => {
    useSettingsStore.setState({ publicApiKey: config, publicApiKeyLoaded: true });
    render(<PublicApiSection />);

    expect(await screen.findByText("tpk_abc")).toBeInTheDocument();
    expect(screen.getByDisplayValue("https://example.com")).toBeInTheDocument();
    expect(screen.getByText(/fetch/)).toBeInTheDocument();
  });

  it("saves newline separated origins", async () => {
    vi.spyOn(useSettingsStore.getState(), "loadPublicApiKey").mockResolvedValueOnce(null);
    const save = vi.spyOn(useSettingsStore.getState(), "savePublicApiKeyOrigins").mockResolvedValueOnce(config);
    render(<PublicApiSection />);

    const input = await screen.findByLabelText("frontend.public_api.origins_label");
    await userEvent.clear(input);
    await userEvent.type(input, "https://example.com\nhttp://localhost:5173");
    await userEvent.click(screen.getByRole("button", { name: "frontend.public_api.save" }));

    await waitFor(() => {
      expect(save).toHaveBeenCalledWith(["https://example.com", "http://localhost:5173"]);
    });
  });

  it("regenerates and revokes with explicit buttons", async () => {
    useSettingsStore.setState({ publicApiKey: config, publicApiKeyLoaded: true });
    vi.spyOn(useSettingsStore.getState(), "loadPublicApiKey").mockResolvedValueOnce(config);
    const regenerate = vi.spyOn(useSettingsStore.getState(), "regeneratePublicApiKey").mockResolvedValueOnce({ ...config, api_key: "tpk_new" });
    const revoke = vi.spyOn(useSettingsStore.getState(), "revokePublicApiKey").mockResolvedValueOnce(undefined);
    render(<PublicApiSection />);

    await screen.findByText("tpk_abc");
    await userEvent.click(screen.getByRole("button", { name: "frontend.public_api.regenerate" }));
    await waitFor(() => expect(regenerate).toHaveBeenCalledTimes(1));

    await userEvent.click(screen.getByRole("button", { name: "frontend.public_api.revoke" }));
    await waitFor(() => expect(revoke).toHaveBeenCalledTimes(1));
  });
});
