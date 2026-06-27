import { beforeEach, describe, expect, it, vi } from "vitest";
import api from "@/lib/api";
import {
  getPublicApiKey,
  regeneratePublicApiKey,
  revokePublicApiKey,
  savePublicApiKeyOrigins,
} from "../settings-api";

vi.mock("@/lib/api", () => ({
  default: {
    get: vi.fn(),
    put: vi.fn(),
    post: vi.fn(),
    delete: vi.fn(),
  },
}));

const mockedApi = vi.mocked(api);

describe("public api key settings service", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("loads the current public api key config", async () => {
    mockedApi.get.mockResolvedValueOnce({ data: null });
    await expect(getPublicApiKey()).resolves.toBeNull();
    expect(mockedApi.get).toHaveBeenCalledWith("/public-api-key");
  });

  it("saves allowed origins", async () => {
    const data = {
      tenant_id: "tenant-1",
      api_key: "tpk_abc",
      allowed_origins: ["https://example.com"],
      created_at: "2026-06-27T00:00:00Z",
      updated_at: "2026-06-27T00:00:00Z",
    };
    mockedApi.put.mockResolvedValueOnce({ data });

    await expect(
      savePublicApiKeyOrigins(["https://example.com"]),
    ).resolves.toEqual(data);
    expect(mockedApi.put).toHaveBeenCalledWith("/public-api-key", {
      allowed_origins: ["https://example.com"],
    });
  });

  it("regenerates and revokes the key", async () => {
    mockedApi.post.mockResolvedValueOnce({ data: { api_key: "tpk_new" } });
    await regeneratePublicApiKey();
    expect(mockedApi.post).toHaveBeenCalledWith("/public-api-key/regenerate");

    mockedApi.delete.mockResolvedValueOnce({ data: undefined });
    await revokePublicApiKey();
    expect(mockedApi.delete).toHaveBeenCalledWith("/public-api-key");
  });
});
