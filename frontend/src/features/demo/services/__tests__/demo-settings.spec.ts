import { beforeEach, describe, expect, it, vi } from "vitest";
import api from "@/lib/api";
import { createDataSource } from "@/lib/data-source";

const metadata = {
  tenantId: "demo-settings",
  name: "Settings Demo",
  plan: "pro" as const,
  status: "active" as const,
  activatedAt: "2026-07-24T12:00:00.000Z",
  expiresAt: "2026-07-26T12:00:00.000Z",
  credentialVersion: 1,
  serverTime: "2026-07-25T12:00:00.000Z",
};

describe("Pro Demo settings adapter", () => {
  beforeEach(() => {
    localStorage.clear();
    vi.restoreAllMocks();
  });

  it("persists local settings and exposes fixed integrations without API calls", async () => {
    const getSpy = vi.spyOn(api, "get");
    const putSpy = vi.spyOn(api, "put");
    const postSpy = vi.spyOn(api, "post");
    const source = createDataSource({ tenantId: metadata.tenantId, tenantPlan: "pro", demo: metadata });

    expect((await source.settings.loadMailbox())?.status).toBe("connected");
    expect((await source.settings.loadTimezoneOptions()).map((item) => item.value)).toEqual(["UTC"]);
    await source.settings.updateReminderSettings({ reminders_enabled: true, warning_days: [5] });
    await source.settings.updateTenantSettings({ locale: "es", timezone: "UTC" });
    await source.settings.updateCodeServices(["secure-mail"]);
    const created = await source.settings.createAccessBlock("12025550103");

    expect((await source.settings.loadReminderSettings()).warning_days).toEqual([5]);
    expect((await source.settings.loadTenantSettings()).locale).toBe("es");
    expect((await source.settings.loadCodeServices()).services.filter((item) => item.is_selected)).toHaveLength(1);
    expect(await source.settings.listAccessBlocks()).toHaveLength(3);
    await source.settings.deleteAccessBlock(created.id);
    expect(await source.settings.listAccessBlocks()).toHaveLength(2);
    expect(getSpy).not.toHaveBeenCalled();
    expect(putSpy).not.toHaveBeenCalled();
    expect(postSpy).not.toHaveBeenCalled();
  });
});
