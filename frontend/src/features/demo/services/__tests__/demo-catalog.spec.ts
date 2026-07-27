import { beforeEach, describe, expect, it, vi } from "vitest";
import api from "@/lib/api";
import type { DemoAuthMetadata } from "@/store/auth";
import { createDataSource } from "@/lib/data-source";
import { createDemoBaseline, readProDemoState } from "../demo-baseline";

const metadata: DemoAuthMetadata = {
  tenantId: "pro-catalog-demo",
  name: "Catalog Demo",
  plan: "pro",
  status: "active",
  activatedAt: "2026-07-24T12:00:00.000Z",
  expiresAt: "2026-07-26T12:00:00.000Z",
  credentialVersion: 1,
  serverTime: "2026-07-25T12:00:00.000Z",
};

beforeEach(() => {
  localStorage.clear();
  vi.restoreAllMocks();
  vi.spyOn(api, "get");
  vi.spyOn(api, "post");
  vi.spyOn(api, "put");
  vi.spyOn(api, "delete");
});

describe("Pro Demo Catalog", () => {
  it("starts with exactly three generic services and deterministic plans", () => {
    const first = createDemoBaseline("pro", metadata);
    const second = createDemoBaseline("pro", metadata);
    const state = readProDemoState(first.plan_specific);

    expect(state?.services).toHaveLength(3);
    expect(state?.plans).toHaveLength(6);
    expect(state?.services.map((service) => service.name)).toEqual([
      "Secure Messaging",
      "Account Access",
      "Verification Hub",
    ]);
    expect(first).toEqual(second);
    expect(JSON.stringify(first)).not.toMatch(/netflix|disney|spotify|hulu/i);
  });

  it("keeps catalog CRUD local, normalized, unique, and persistent", async () => {
    const source = createDataSource({
      tenantId: metadata.tenantId,
      tenantPlan: metadata.plan,
      demo: metadata,
    });
    const catalog = source.catalog;
    const initial = await catalog.listServices();
    const created = await catalog.createService({ name: "  New Service  " });
    const renamed = await catalog.updateService(created.id, { name: "New Service Renamed" });
    const plan = await catalog.createPlan(renamed.id, { name: "  Starter Plan " });

    expect(initial).toHaveLength(3);
    expect(renamed.name).toBe("New Service Renamed");
    expect(plan.name).toBe("Starter Plan");
    await expect(catalog.createService({ name: " new service renamed " })).rejects.toMatchObject({
      code: "service_name_already_exists",
    });
    await expect(catalog.createPlan(renamed.id, { name: "STARTER PLAN" })).rejects.toMatchObject({
      code: "plan_name_already_exists",
    });

    const reloaded = createDataSource({
      tenantId: metadata.tenantId,
      tenantPlan: metadata.plan,
      demo: metadata,
    });
    expect((await reloaded.catalog.listServices()).find((item) => item.id === created.id)?.name).toBe(
      "New Service Renamed",
    );
    expect(await reloaded.catalog.listPlans(created.id)).toEqual([plan]);
    expect(api.get).not.toHaveBeenCalled();
    expect(api.post).not.toHaveBeenCalled();
    expect(api.put).not.toHaveBeenCalled();
    expect(api.delete).not.toHaveBeenCalled();
  });

  it("previews and cascades service deletion without orphan plans or relations", async () => {
    const source = createDataSource({
      tenantId: metadata.tenantId,
      tenantPlan: metadata.plan,
      demo: metadata,
    });
    await source.catalog.listServices();
    const state = source.workspace!.read()!;
    const pro = readProDemoState(state.plan_specific)!;
    const target = pro.services[0];
    const targetPlan = pro.plans.find((plan) => plan.service_id === target.id)!;
    const injectedSubscription = {
      ...pro.subscriptions[0],
      id: "sub-active",
      tenant_id: metadata.tenantId,
      service_id: target.id,
      plan_id: targetPlan.id,
      client_id: pro.clients[0].id,
      status: "active" as const,
      streaming_email: "active@example.com",
    };
    source.workspace!.updatePlanSpecific((current) => ({
      ...current,
      subscriptions: [injectedSubscription],
    }));

    const preview = await source.catalog.getServiceDeletePreview(target.id);
    expect(preview.affected_plan_count).toBe(2);
    expect(preview.active_subscription_count).toBe(1);
    expect(preview.active_subscriptions[0].streaming_email).toBe("active@example.com");

    await source.catalog.deleteService(target.id);
    const after = readProDemoState(source.workspace!.read()!.plan_specific)!;
    expect(after.services.some((service) => service.id === target.id)).toBe(false);
    expect(after.plans.some((plan) => plan.service_id === target.id)).toBe(false);
    expect(after.subscriptions).toHaveLength(0);
  });

  it("previews plan relationships from the current workspace", async () => {
    const source = createDataSource({
      tenantId: metadata.tenantId,
      tenantPlan: metadata.plan,
      demo: metadata,
    });
    await source.catalog.listServices();
    const state = readProDemoState(source.workspace!.read()!.plan_specific)!;
    const service = state.services[0];
    const plan = state.plans.find((item) => item.service_id === service.id)!;

    const preview = await source.catalog.getPlanDeletePreview(service.id, plan.id);
    const related = state.subscriptions.filter((subscription) => subscription.plan_id === plan.id);
    expect(preview.total_subscription_count).toBe(related.length);
    expect(preview.active_subscription_count).toBe(
      related.filter((subscription) => subscription.status === "active").length,
    );
  });

  it("does not create a Starter catalog baseline", async () => {
    const starter = createDataSource({
      tenantId: "starter-catalog-demo",
      tenantPlan: "starter",
      demo: { ...metadata, tenantId: "starter-catalog-demo", plan: "starter" },
    });

    await starter.dashboard.load();
    expect(starter.catalog.storage).toBe("workspace");
    expect(starter.workspace!.read()!.plan_specific).not.toHaveProperty("services");
  });
});
