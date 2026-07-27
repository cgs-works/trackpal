import { beforeEach, describe, expect, it, vi } from "vitest";
import api from "@/lib/api";
import type { DemoAuthMetadata } from "@/store/auth";
import { createDataSource } from "@/lib/data-source";
import { createDemoBaseline, readProDemoState } from "../demo-baseline";

const metadata: DemoAuthMetadata = {
  tenantId: "pro-dashboard-demo",
  name: "Dashboard Demo",
  plan: "pro",
  status: "active",
  activatedAt: "2026-07-24T12:00:00.000Z",
  expiresAt: "2026-07-26T12:00:00.000Z",
  credentialVersion: 1,
  serverTime: "2026-07-25T12:00:00.000Z",
};

describe("Pro Demo dashboard data source", () => {
  beforeEach(() => {
    localStorage.clear();
    vi.restoreAllMocks();
  });

  it("derives every Pro metric from the current workspace", async () => {
    const getSpy = vi.spyOn(api, "get");
    const source = createDataSource({
      tenantId: metadata.tenantId,
      tenantPlan: metadata.plan,
      demo: metadata,
    });

    await expect(source.dashboard.load()).resolves.toMatchObject({
      active_clients: 3,
      catalog_services: 6,
      active_subscriptions: 5,
      subscriptions_expiring_soon: 3,
      mailbox_status: "connected",
      enabled_code_services: ["Disney+", "HBO Max", "Netflix", "Prime Video", "Spotify", "Universal+"],
      access_control_count: 2,
      reminders_enabled: false,
    });

    await source.settings.updateReminderSettings({ reminders_enabled: true });
    await source.settings.updateCodeServices(["netflix"]);
    await source.settings.createAccessBlock("12025550103");
    await expect(source.dashboard.load()).resolves.toMatchObject({
      enabled_code_services: ["Netflix"],
      access_control_count: 3,
      reminders_enabled: true,
    });

    const state = readProDemoState(source.workspace!.read()!.plan_specific)!;
    await source.crud.clients.deactivate(state.clients[0].id);
    await source.subscriptions.cancel(state.subscriptions.find((item) => item.status === "active")!.id);
    await source.catalog.createService({ name: "Local Service" });

    await expect(source.dashboard.load()).resolves.toMatchObject({
      active_clients: 2,
      catalog_services: 7,
      active_subscriptions: 4,
      subscriptions_expiring_soon: 3,
    });

    source.workspace!.reset(metadata, createDemoBaseline);
    await expect(source.dashboard.load()).resolves.toMatchObject({
      active_clients: 3,
      catalog_services: 6,
      active_subscriptions: 5,
      subscriptions_expiring_soon: 3,
    });

    expect(getSpy).not.toHaveBeenCalled();
  });
});
