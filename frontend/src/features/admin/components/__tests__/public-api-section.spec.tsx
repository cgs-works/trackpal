import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { PublicApiSection } from "../public-api-section";
import { useSettingsStore } from "@/store/settings";

vi.mock("@/i18n", () => ({
  t: (key: string) => key,
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
    Object.defineProperty(navigator, "clipboard", {
      configurable: true,
      value: { writeText: vi.fn().mockResolvedValue(undefined) },
    });
  });

  it("loads and keeps the existing key hidden until requested", async () => {
    const user = userEvent.setup();
    useSettingsStore.setState({ publicApiKey: config, publicApiKeyLoaded: true });
    render(<PublicApiSection />);

    expect(await screen.findByText("tpk_••••••••••••••••••")).toBeInTheDocument();
    expect(screen.getByText("https://example.com")).toBeInTheDocument();
    expect(screen.getByText(/fetch/)).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "frontend.public_api.show" }));
    expect(screen.getByText("tpk_abc")).toBeInTheDocument();
  });

  it("creates the key with the first authorized website", async () => {
    const user = userEvent.setup();
    vi.spyOn(useSettingsStore.getState(), "loadPublicApiKey").mockResolvedValueOnce(null);
    const save = vi.spyOn(useSettingsStore.getState(), "savePublicApiKeyOrigins").mockResolvedValueOnce(config);
    render(<PublicApiSection />);

    const input = await screen.findByLabelText("frontend.public_api.site_label");
    await user.type(input, "https://example.com");
    await user.click(screen.getByRole("button", { name: "frontend.public_api.create_key" }));

    await waitFor(() => {
      expect(save).toHaveBeenCalledWith(["https://example.com"]);
    });
  });

  it("edits sites and deletes the key with confirmation", async () => {
    const user = userEvent.setup();
    useSettingsStore.setState({ publicApiKey: config, publicApiKeyLoaded: true });
    const save = vi.spyOn(useSettingsStore.getState(), "savePublicApiKeyOrigins").mockResolvedValueOnce({
      ...config,
      allowed_origins: ["https://example.com", "http://localhost:5173"],
    });
    const revoke = vi.spyOn(useSettingsStore.getState(), "revokePublicApiKey").mockResolvedValueOnce(undefined);
    render(<PublicApiSection />);

    const input = await screen.findByLabelText("frontend.public_api.sites_label");
    await user.type(input, "http://localhost:5173");
    await user.click(screen.getByRole("button", { name: "frontend.public_api.add_site" }));
    await user.click(screen.getByRole("button", { name: "frontend.public_api.save_changes" }));
    await waitFor(() => expect(save).toHaveBeenCalledWith(["https://example.com", "http://localhost:5173"]));

    await user.click(screen.getAllByRole("button", { name: "frontend.public_api.delete_key" })[0]);
    expect(await screen.findByText("frontend.public_api.delete_key_title")).toBeInTheDocument();
    await user.click(screen.getAllByRole("button", { name: "frontend.public_api.delete_key" }).at(-1)!);
    await waitFor(() => expect(revoke).toHaveBeenCalledTimes(1));
  });
});
