import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { buildDeveloperHandoffPackage, PublicApiSection } from "../public-api-section";
import { useSettingsStore } from "@/store/settings";
import api from "@/lib/api";
import { createDataSource } from "@/lib/data-source";

const mockUseAuthStore = vi.hoisted(() => vi.fn());

vi.mock("@/store/auth", () => ({
  useAuthStore: mockUseAuthStore,
}));

vi.mock("@/i18n", () => ({
  t: (key: string) => key,
}));

const clipboardWriteText = vi.fn().mockResolvedValue(undefined);

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
    mockUseAuthStore.mockReturnValue({
      dataSource: { mode: "production", settings: {} },
    });
    useSettingsStore.getState().clearSettingsCache();
    Object.defineProperty(navigator, "clipboard", {
      configurable: true,
      value: { writeText: clipboardWriteText },
    });
  });

  it("builds a complete handoff package without the tenant key", () => {
    const packageText = buildDeveloperHandoffPackage("https://api.example.com/api/v1", ["https://example.com"]);

    expect(packageText).toContain("YOUR_PUBLIC_API_KEY");
    expect(packageText).not.toContain("tpk_abc");
    expect(packageText).toContain("frontend.public_api.lang_html");
    expect(packageText).toContain("frontend.public_api.lang_alpine");
  });

  it("includes Iconify icon reference guidance in handoff", () => {
    const packageText = buildDeveloperHandoffPackage("https://api.example.com/api/v1", ["https://example.com"]);

    expect(packageText).toContain("service.icon");
    expect(packageText).toContain("https://api.iconify.design");
    expect(packageText).toContain("prefix:name");
    expect(packageText).toContain("YOUR_PUBLIC_API_KEY");
    expect(packageText).not.toContain("tpk_abc");
  });

  it("loads and keeps the existing key hidden until requested", async () => {
    const user = userEvent.setup();
    const clipboardSpy = vi.spyOn(navigator.clipboard, "writeText");
    useSettingsStore.setState({ publicApiKey: config, publicApiKeyLoaded: true });
    render(<PublicApiSection />);

    expect(await screen.findByText("tpk_••••••••••••••••••")).toBeInTheDocument();
    expect(screen.getByText("https://example.com")).toBeInTheDocument();
    expect(screen.getByText(/fetch/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "frontend.public_api.copy_handoff" })).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "frontend.public_api.copy_handoff" }));
    await waitFor(() => expect(clipboardSpy).toHaveBeenCalled());
    expect(clipboardSpy.mock.calls[0][0]).toContain("YOUR_PUBLIC_API_KEY");
    expect(clipboardSpy.mock.calls[0][0]).not.toContain("tpk_abc");

    await user.click(screen.getByRole("button", { name: "frontend.public_api.show" }));
    expect(screen.getByText("tpk_abc")).toBeInTheDocument();
  });

  it("keeps every Public API control disabled for Pro Demo Accounts", async () => {
    const metadata = {
      tenantId: "demo-public-api",
      name: "Public API Demo",
      plan: "pro" as const,
      status: "active" as const,
      activatedAt: "2026-07-24T12:00:00.000Z",
      expiresAt: "2026-07-26T12:00:00.000Z",
      credentialVersion: 1,
      serverTime: "2026-07-25T12:00:00.000Z",
    };
    const getSpy = vi.spyOn(api, "get");
    const putSpy = vi.spyOn(api, "put");
    const postSpy = vi.spyOn(api, "post");
    const deleteSpy = vi.spyOn(api, "delete");
    mockUseAuthStore.mockReturnValue({
      dataSource: createDataSource({
        tenantId: metadata.tenantId,
        tenantPlan: metadata.plan,
        demo: metadata,
      }),
    });

    render(<PublicApiSection />);

    expect(await screen.findByText("frontend.public_api.demo_title")).toBeInTheDocument();
    expect(screen.getByText("frontend.public_api.demo_description")).toBeInTheDocument();
    expect(screen.getByRole("textbox", { name: "frontend.public_api.site_label" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "frontend.public_api.create_key" })).toBeDisabled();
    expect(screen.getByRole("textbox", { name: "frontend.public_api.key_label" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "frontend.public_api.show" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "frontend.public_api.copy" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "frontend.public_api.delete_key" })).toBeDisabled();
    expect(getSpy).not.toHaveBeenCalled();
    expect(putSpy).not.toHaveBeenCalled();
    expect(postSpy).not.toHaveBeenCalled();
    expect(deleteSpy).not.toHaveBeenCalled();
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
