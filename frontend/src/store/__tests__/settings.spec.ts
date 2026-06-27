import { beforeEach, describe, expect, it, vi } from "vitest";
import { useSettingsStore } from "../settings";
import {
  getPublicApiKey,
  regeneratePublicApiKey,
  revokePublicApiKey,
  savePublicApiKeyOrigins,
} from "@/features/admin/services/settings-api";

vi.mock("@/features/admin/services/settings-api", async (importOriginal) => {
  const actual =
    await importOriginal<typeof import("@/features/admin/services/settings-api")>();
  return {
    ...actual,
    getPublicApiKey: vi.fn(),
    savePublicApiKeyOrigins: vi.fn(),
    regeneratePublicApiKey: vi.fn(),
    revokePublicApiKey: vi.fn(),
  };
});

const config = {
  tenant_id: "tenant-1",
  api_key: "tpk_abc",
  allowed_origins: ["https://example.com"],
  created_at: "2026-06-27T00:00:00Z",
  updated_at: "2026-06-27T00:00:00Z",
};

describe("settings store public api key", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    useSettingsStore.getState().clearSettingsCache();
  });

  it("deduplicates public api key loads", async () => {
    vi.mocked(getPublicApiKey).mockResolvedValueOnce(config);

    const [first, second] = await Promise.all([
      useSettingsStore.getState().loadPublicApiKey(),
      useSettingsStore.getState().loadPublicApiKey(),
    ]);

    expect(first).toEqual(config);
    expect(second).toEqual(config);
    expect(getPublicApiKey).toHaveBeenCalledTimes(1);
    expect(useSettingsStore.getState().publicApiKey).toEqual(config);
  });

  it("updates, regenerates, revokes, and clears public api key state", async () => {
    vi.mocked(savePublicApiKeyOrigins).mockResolvedValueOnce(config);
    await expect(
      useSettingsStore.getState().savePublicApiKeyOrigins([
        "https://example.com",
      ]),
    ).resolves.toEqual(config);
    expect(useSettingsStore.getState().publicApiKey).toEqual(config);

    const regenerated = { ...config, api_key: "tpk_new" };
    vi.mocked(regeneratePublicApiKey).mockResolvedValueOnce(regenerated);
    await expect(
      useSettingsStore.getState().regeneratePublicApiKey(),
    ).resolves.toEqual(regenerated);
    expect(useSettingsStore.getState().publicApiKey?.api_key).toBe("tpk_new");

    vi.mocked(revokePublicApiKey).mockResolvedValueOnce(undefined);
    await useSettingsStore.getState().revokePublicApiKey();
    expect(useSettingsStore.getState().publicApiKey).toBeNull();
    expect(useSettingsStore.getState().publicApiKeyLoaded).toBe(true);

    useSettingsStore.getState().clearSettingsCache();
    expect(useSettingsStore.getState().publicApiKeyLoaded).toBe(false);
  });
});
