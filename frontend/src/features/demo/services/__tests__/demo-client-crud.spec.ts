import { beforeEach, describe, expect, it, vi } from "vitest";
import {
  createDemoBaseline,
  readProDemoState,
} from "../demo-baseline";
import type { DemoAuthMetadata } from "@/store/auth";
import { createDataSource } from "@/lib/data-source";
import type { ClientCreate } from "@/features/admin/services/client-api";
import api from "@/lib/api";

const metadata: DemoAuthMetadata = {
  tenantId: "pro-demo-1",
  name: "Northwind Demo",
  plan: "pro",
  status: "active",
  activatedAt: "2026-07-24T12:00:00.000Z",
  expiresAt: "2026-07-26T12:00:00.000Z",
  credentialVersion: 1,
  serverTime: "2026-07-25T12:00:00.000Z",
};

const validCreate: ClientCreate = {
  full_name: "Nora Example",
  local_username: "nora_example",
  phone: "+1 (415) 555-2676",
  password: "not-persisted",
};

beforeEach(() => {
  localStorage.clear();
  vi.restoreAllMocks();
});

describe("Pro Demo Clients baseline", () => {
  it("contains exactly five deterministic clients with active and inactive coverage", () => {
    const first = createDemoBaseline("pro", metadata);
    const second = createDemoBaseline("pro", metadata);
    const clients = readProDemoState(first.plan_specific)?.clients ?? [];

    expect(clients).toHaveLength(5);
    expect(clients.filter((client) => client.is_active)).toHaveLength(3);
    expect(clients.filter((client) => !client.is_active)).toHaveLength(2);
    expect(first).toEqual(second);
    expect(clients.every((client) => client.tenant_id === metadata.tenantId)).toBe(true);
    expect(JSON.stringify(first)).not.toMatch(/password|token|session|credential/i);
  });
});

describe("Pro Demo Clients data source", () => {
  it("keeps CRUD local, normalizes phone values, and persists mutations", async () => {
    const source = createDataSource({
      tenantId: metadata.tenantId,
      tenantPlan: "pro",
      demo: metadata,
    });
    const getSpy = vi.spyOn(api, "get");
    const postSpy = vi.spyOn(api, "post");
    const repository = source.workspace!;
    const clients = source.crud.clients;

    await expect(clients.list()).resolves.toHaveLength(5);
    const created = await clients.create(validCreate);
    expect(created.phone).toBe("14155552676");
    expect(created.username).toBe("demo_nora_example");
    expect(repository.read()?.plan_specific).toHaveProperty("clients");
    expect(JSON.stringify(repository.read())).not.toContain("not-persisted");
    expect(getSpy).not.toHaveBeenCalled();
    expect(postSpy).not.toHaveBeenCalled();

    await clients.deactivate(created.id);
    await expect(clients.delete(created.id)).resolves.toBeUndefined();
    await expect(clients.list()).resolves.toHaveLength(5);

    const reloaded = createDataSource({
      tenantId: metadata.tenantId,
      tenantPlan: "pro",
      demo: metadata,
    });
    await expect(reloaded.crud.clients.list()).resolves.toHaveLength(5);
    await expect(reloaded.crud.clients.list()).resolves.not.toContainEqual(created);
  });

  it("enforces username, phone, and relation-safe delete rules", async () => {
    const source = createDataSource({
      tenantId: metadata.tenantId,
      tenantPlan: "pro",
      demo: metadata,
    });
    const clients = source.crud.clients;
    const baseline = await clients.list();

    await expect(
      clients.create({ ...validCreate, local_username: baseline[0].username.replace("demo_", "") }),
    ).rejects.toMatchObject({ code: "client_local_username_exists" });
    await expect(
      clients.create({ ...validCreate, local_username: "unique_phone", phone: "14155552671" }),
    ).rejects.toMatchObject({ code: "phone_already_registered" });
    await expect(clients.delete(baseline[0].id)).rejects.toMatchObject({
      code: "client_delete_active",
    });

    await clients.deactivate(baseline[1].id);
    const beforeDelete = readProDemoState(source.workspace!.read()!.plan_specific)!;
    const relatedSubscriptionIds = beforeDelete.subscriptions
      .filter((subscription) => subscription.client_id === baseline[1].id)
      .map((subscription) => subscription.id);

    await expect(clients.delete(baseline[1].id)).resolves.toBeUndefined();
    const afterDelete = readProDemoState(source.workspace!.read()!.plan_specific)!;
    expect(afterDelete.clients.some((client) => client.id === baseline[1].id)).toBe(false);
    expect(afterDelete.subscriptions.some((subscription) => relatedSubscriptionIds.includes(subscription.id))).toBe(false);
  });
});
