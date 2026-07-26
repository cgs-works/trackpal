import { beforeEach, describe, expect, it, vi } from "vitest";
import api from "@/lib/api";
import type { DemoAuthMetadata } from "@/store/auth";
import { createDataSource } from "@/lib/data-source";
import { createDemoBaseline, readProDemoState } from "../demo-baseline";

const metadata: DemoAuthMetadata = {
  tenantId: "pro-subscriptions-demo",
  name: "Subscriptions Demo",
  plan: "pro",
  status: "active",
  activatedAt: "2026-07-24T12:00:00.000Z",
  expiresAt: "2026-07-26T12:00:00.000Z",
  credentialVersion: 1,
  serverTime: "2026-07-25T12:00:00.000Z",
};

function atOffset(days: number): string {
  return new Date(new Date(metadata.activatedAt!).getTime() + days * 86_400_000).toISOString();
}

beforeEach(() => {
  localStorage.clear();
  vi.restoreAllMocks();
});

describe("Pro Demo Subscriptions baseline", () => {
  it("contains eight deterministic linked records with lifecycle coverage", () => {
    const first = createDemoBaseline("pro", metadata);
    const second = createDemoBaseline("pro", metadata);
    const state = readProDemoState(first.plan_specific)!;

    expect(state.subscriptions).toHaveLength(8);
    expect(first).toEqual(second);
    expect(new Set(state.subscriptions.map((subscription) => subscription.status))).toEqual(
      new Set(["active", "expired", "cancelled"]),
    );
    expect(state.subscriptions.filter((subscription) => subscription.status === "active")).toHaveLength(5);
    expect(state.subscriptions.filter((subscription) => subscription.status === "expired")).toHaveLength(1);
    expect(state.subscriptions.filter((subscription) => subscription.status === "cancelled")).toHaveLength(2);
    expect(state.subscriptions.find((subscription) => subscription.streaming_email === "demo.expiring.7@example.test")?.expires_at).toBe(
      atOffset(7),
    );
    expect(state.subscriptions.find((subscription) => subscription.streaming_email === "demo.expiring.3@example.test")?.expires_at).toBe(
      atOffset(3),
    );
    expect(state.subscriptions.find((subscription) => subscription.streaming_email === "demo.expiring.1@example.test")?.expires_at).toBe(
      atOffset(1),
    );
    expect(
      state.subscriptions.every(
        (subscription) =>
          state.clients.some((client) => client.id === subscription.client_id) &&
          state.services.some((service) => service.id === subscription.service_id) &&
          state.plans.some((plan) => plan.id === subscription.plan_id && plan.service_id === subscription.service_id),
      ),
    ).toBe(true);
    expect(JSON.stringify(first)).not.toMatch(/netflix|disney|spotify|hulu/i);
  });

  it("does not initialize subscription data for Starter workspaces", () => {
    const starterMetadata = { ...metadata, tenantId: "starter-subscriptions-demo", plan: "starter" as const };
    const baseline = createDemoBaseline("starter", starterMetadata);
    expect(baseline.plan_specific).not.toHaveProperty("subscriptions");
  });
});

describe("Pro Demo Subscriptions data source", () => {
  it("supports local filtering, CRUD, lifecycle transitions, masked credentials, and reset", async () => {
    const source = createDataSource({
      tenantId: metadata.tenantId,
      tenantPlan: metadata.plan,
      demo: metadata,
    });
    const getSpy = vi.spyOn(api, "get");
    const postSpy = vi.spyOn(api, "post");
    const putSpy = vi.spyOn(api, "put");

    const initial = await source.subscriptions.list();
    expect(initial).toHaveLength(8);
    expect(initial[0]).not.toHaveProperty("streaming_password");

    const expiring = await source.subscriptions.list({ quick_filter: "expiring" });
    expect(expiring).toHaveLength(3);

    const service = readProDemoState(source.workspace!.read()!.plan_specific)!.services[0];
    const plan = readProDemoState(source.workspace!.read()!.plan_specific)!.plans.find(
      (item) => item.service_id === service.id,
    )!;
    const client = readProDemoState(source.workspace!.read()!.plan_specific)!.clients[0];
    const created = await source.subscriptions.create({
      client_id: client.id,
      service_id: service.id,
      plan_id: plan.id,
      streaming_email: "local.new@example.test",
      streaming_password: "fictional-secret",
      profile_name: "Demo Profile",
      profile_pin: "1234",
      duration_type: "1_month",
      starts_at: atOffset(0),
    });
    expect(created.status).toBe("active");
    expect(created.has_password).toBe(true);
    expect(created.has_pin).toBe(true);
    expect(await source.subscriptions.reveal(created.id)).toEqual({
      streaming_password: "fictional-secret",
      profile_pin: "1234",
    });

    const cancelled = await source.subscriptions.cancel(created.id);
    expect(cancelled.status).toBe("cancelled");
    const reactivated = await source.subscriptions.reactivate(created.id, "3_months");
    expect(reactivated.status).toBe("active");
    expect(reactivated.duration_type).toBe("3_months");
    const renewed = await source.subscriptions.renew(reactivated.id, "1_month");
    expect(new Date(renewed.expires_at).getTime()).toBe(
      new Date(reactivated.expires_at).getTime() + 30 * 86_400_000,
    );

    await expect(
      source.subscriptions.create({
        ...{
          client_id: client.id,
          service_id: service.id,
          plan_id: plan.id,
          streaming_email: "invalid@example.test",
          duration_type: "custom",
          starts_at: atOffset(0),
        },
      }),
    ).rejects.toMatchObject({ code: "subscription_validation_failed" });

    source.workspace!.reset(metadata, createDemoBaseline);
    expect(await source.subscriptions.list()).toHaveLength(8);
    expect(getSpy).not.toHaveBeenCalled();
    expect(postSpy).not.toHaveBeenCalled();
    expect(putSpy).not.toHaveBeenCalled();
  });
});
