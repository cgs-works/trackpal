import { beforeEach, describe, expect, it, vi } from "vitest";
import api from "@/lib/api";
import { createDataSource } from "@/lib/data-source";
import { createDemoBaseline } from "../demo-baseline";

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
    const timezoneOptions = await source.settings.loadTimezoneOptions();
    expect(timezoneOptions.map((item) => item.value)).toContain("UTC");
    expect(timezoneOptions.map((item) => item.value)).toContain("America/Caracas");
    await source.settings.updateReminderSettings({ reminders_enabled: true, warning_days: [5] });
    await source.settings.updateTenantSettings({ locale: "es", timezone: "UTC" });
    await source.settings.updateCodeServices(["netflix"]);
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

  it("rejects duplicate access blocks without changing the local workspace", async () => {
    const source = createDataSource({ tenantId: metadata.tenantId, tenantPlan: "pro", demo: metadata });

    const before = await source.settings.listAccessBlocks();
    await expect(source.settings.createAccessBlock(before[0].phone ?? "")).rejects.toThrow("access_block_duplicate");
    await expect(source.settings.listAccessBlocks()).resolves.toHaveLength(before.length);
  });

  it("matches production validation for timezone, locale, reminder time, and recipient mode", async () => {
    const source = createDataSource({ tenantId: metadata.tenantId, tenantPlan: "pro", demo: metadata });

    await expect(source.settings.updateTenantSettings({ timezone: "Not/A_Timezone" })).rejects.toThrow();
    await expect(source.settings.updateTenantSettings({ locale: "fr" })).rejects.toThrow();
    await expect(source.settings.updateReminderSettings({ reminder_time: "25:00" })).rejects.toThrow();
    await expect(source.settings.updateReminderSettings({ recipient_mode: "unknown" as never })).rejects.toThrow();

    await expect(source.settings.updateTenantSettings({ timezone: "America/Caracas", locale: "ES" })).resolves.toMatchObject({
      timezone: "America/Caracas",
      locale: "es",
    });
    await expect(source.settings.updateReminderSettings({ reminder_time: "23:59", recipient_mode: "both" })).resolves.toMatchObject({
      reminder_time: "23:59",
      recipient_mode: "both",
    });
  });

  it("restores Pro timezone and reminder settings through Demo reset", async () => {
    const source = createDataSource({ tenantId: metadata.tenantId, tenantPlan: "pro", demo: metadata });

    await source.settings.updateTenantSettings({ timezone: "America/Caracas" });
    await source.settings.updateReminderSettings({ reminders_enabled: true, reminder_time: "23:59" });
    source.workspace?.reset(metadata, createDemoBaseline);

    await expect(source.settings.loadTenantSettings()).resolves.toMatchObject({ timezone: "UTC" });
    await expect(source.settings.loadReminderSettings()).resolves.toMatchObject({
      reminders_enabled: false,
      reminder_time: "09:00",
    });
  });

  it("does not create or expose a Public API key in a Demo Account", async () => {
    const source = createDataSource({ tenantId: metadata.tenantId, tenantPlan: "pro", demo: metadata });

    await expect(source.settings.loadPublicApiKey()).resolves.toBeNull();
    await expect(source.settings.savePublicApiKeyOrigins(["https://example.test"])).rejects.toThrow("demo_public_api_blocked");
    await expect(source.settings.regeneratePublicApiKey()).rejects.toThrow("demo_public_api_blocked");
    await expect(source.settings.revokePublicApiKey()).rejects.toThrow("demo_public_api_blocked");
  });

  it("persists profile, locale, code services, and access control locally for Starter and Pro", async () => {
    const getSpy = vi.spyOn(api, "get");
    const putSpy = vi.spyOn(api, "put");

    for (const plan of ["starter", "pro"] as const) {
      const source = createDataSource({
        tenantId: `profile-${plan}`,
        tenantPlan: plan,
        demo: { ...metadata, tenantId: `profile-${plan}`, plan },
      });

      const initial = await source.settings.loadProfile();
      expect(initial.full_name).toBe("Settings Demo");

      const updated = await source.settings.updateProfile({
        full_name: `${plan} Business`,
        email: `${plan}@example.test`,
        phone: "12025550199",
      });

      expect(updated.full_name).toBe(`${plan} Business`);
      expect((await source.settings.loadProfile()).email).toBe(`${plan}@example.test`);
      await source.settings.updateTenantSettings({ locale: "es" });
      await source.settings.updateCodeServices(["netflix"]);
      const created = await source.settings.createAccessBlock("12025550199");
      expect((await source.settings.loadTenantSettings()).locale).toBe("es");
      expect((await source.settings.loadCodeServices()).services.filter((item) => item.is_selected)).toHaveLength(1);
      expect((await source.settings.listAccessBlocks()).some((item) => item.id === created.id)).toBe(true);
    }

    expect(getSpy).not.toHaveBeenCalled();
    expect(putSpy).not.toHaveBeenCalled();
  });

  it("loads currency options from the catalog without API calls", async () => {
    const getSpy = vi.spyOn(api, "get");
    const source = createDataSource({ tenantId: metadata.tenantId, tenantPlan: "pro", demo: metadata });

    const result = await source.settings.loadCurrencyOptions();
    expect(result.countries.length).toBeGreaterThan(0);
    expect(result.currencies.length).toBeGreaterThan(0);
    expect(result.currencies.some((c) => c.code === "USD")).toBe(true);
    expect(result.countries.some((c) => c.code === "VE")).toBe(true);
    expect(getSpy).not.toHaveBeenCalled();
  });

  it("validates country and currency codes against the catalog", async () => {
    const source = createDataSource({ tenantId: metadata.tenantId, tenantPlan: "pro", demo: metadata });

    await expect(source.settings.updateTenantSettings({ country: "ZZ" })).rejects.toThrow();
    await expect(source.settings.updateTenantSettings({ currency: "ZZZ" })).rejects.toThrow();

    await expect(
      source.settings.updateTenantSettings({ country: "ve", currency: "VES" }),
    ).resolves.toMatchObject({ country: "VE", currency: "VES" });
  });

  it("defaults country to US and currency to null in starter tenant settings", async () => {
    const starterSource = createDataSource({
      tenantId: "starter-settings",
      tenantPlan: "starter",
      demo: { ...metadata, tenantId: "starter-settings", plan: "starter" },
    });

    const settings = await starterSource.settings.loadTenantSettings();
    expect(settings.country).toBe("US");
    expect(settings.currency).toBeNull();
  });

  it("defaults country to US and currency to USD in pro tenant settings", async () => {
    const source = createDataSource({ tenantId: metadata.tenantId, tenantPlan: "pro", demo: metadata });

    const settings = await source.settings.loadTenantSettings();
    expect(settings.country).toBe("US");
    expect(settings.currency).toBe("USD");
  });
});
