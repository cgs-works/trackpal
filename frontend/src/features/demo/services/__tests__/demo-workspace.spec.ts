import { beforeEach, describe, expect, it, vi } from "vitest";
import {
  clearDemoWorkspace,
  createDemoWorkspaceRepository,
  DEMO_WORKSPACE_KEY_PREFIX,
  DEMO_WORKSPACE_SCHEMA_VERSION,
  type DemoWorkspaceEnvelope,
  type DemoWorkspaceRepository,
  type PlanBaselineFactory,
} from "../demo-workspace";
import type { DemoAuthMetadata } from "@/store/auth";

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

const baseMetadata = (overrides?: Partial<DemoAuthMetadata>): DemoAuthMetadata => ({
  tenantId: "demo-tenant-1",
  name: "Test Demo",
  plan: "starter",
  status: "active",
  activatedAt: "2026-07-01T00:00:00Z",
  expiresAt: "2026-08-01T00:00:00Z",
  credentialVersion: 1,
  serverTime: "2026-07-25T12:00:00Z",
  ...overrides,
});

const proMetadata = (overrides?: Partial<DemoAuthMetadata>): DemoAuthMetadata =>
  baseMetadata({ ...overrides, plan: "pro", tenantId: overrides?.tenantId ?? "demo-tenant-2" });

/** In-memory StorageLike for tests. */
function fakeStorage(): Storage {
  const store = new Map<string, string>();
  return {
    get length() {
      return store.size;
    },
    clear: () => store.clear(),
    getItem: (key: string) => store.get(key) ?? null,
    key: (index: number) => Array.from(store.keys())[index] ?? null,
    removeItem: (key: string) => {
      store.delete(key);
    },
    setItem: (key: string, value: string) => {
      store.set(key, value);
    },
  };
}

function baselineFactory(value: Record<string, unknown>, version = 9): PlanBaselineFactory {
  return vi.fn(() => ({
    plan_specific: value,
    tour_state: { baselineTour: false },
    baseline_version: version,
  }));
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("DemoWorkspaceRepository", () => {
  let storage: Storage;
  let repo: DemoWorkspaceRepository;
  let fetchSpy: ReturnType<typeof vi.spyOn>;
  const TENANT_ID = "demo-tenant-1";

  beforeEach(() => {
    storage = fakeStorage();
    repo = createDemoWorkspaceRepository(TENANT_ID, storage);
    fetchSpy = vi.spyOn(globalThis, "fetch").mockImplementation(
      () => Promise.resolve(new Response(null, { status: 200 })),
    );
  });

  afterEach(() => {
    fetchSpy.mockRestore();
    vi.useRealTimers();
  });

  describe("keys / isolation", () => {
    it("uses a key prefixed with the constant and scoped to tenant id", () => {
      expect(repo.key).toBe(`${DEMO_WORKSPACE_KEY_PREFIX}${TENANT_ID}`);
    });

    it("isolates workspaces by tenant id", () => {
      const otherTenant = "other-tenant";
      const repoA = createDemoWorkspaceRepository(TENANT_ID, storage);
      const repoB = createDemoWorkspaceRepository(otherTenant, storage);

      repoA.ensure(baseMetadata());
      expect(repoA.read()).not.toBeNull();
      expect(repoB.read()).toBeNull();

      expect(repoA.key).not.toBe(repoB.key);
    });

    it("uses last-write-wins for same-tenant tabs without crossing tenant keys", () => {
      const firstTab = createDemoWorkspaceRepository(TENANT_ID, storage);
      const secondTab = createDemoWorkspaceRepository(TENANT_ID, storage);
      const otherTenant = createDemoWorkspaceRepository("other-tenant", storage);

      firstTab.ensure(baseMetadata(), baselineFactory({ owner: "first" }));
      secondTab.updatePlanSpecific(() => ({ owner: "second" }));
      otherTenant.ensure(baseMetadata({ tenantId: "other-tenant" }), baselineFactory({ owner: "other" }));

      expect(firstTab.read()?.plan_specific).toEqual({ owner: "second" });
      expect(otherTenant.read()?.plan_specific).toEqual({ owner: "other" });
      expect(firstTab.read()?.tenant_id).toBe(TENANT_ID);
    });

    it("does not store tokens, passwords, credentials, session identifiers, or chat transcripts", () => {
      repo.ensure(baseMetadata());
      const envelope = repo.read()!;

      const serialized = JSON.stringify(envelope);
      expect(serialized).not.toContain("token");
      expect(serialized).not.toContain("password");
      expect(serialized).not.toContain("credential");
      expect(serialized).not.toContain("session");
      expect(serialized).not.toContain("chat");
    });
  });

  describe("schema / envelope shape", () => {
    it("creates an envelope with the correct schema version", () => {
      repo.ensure(baseMetadata());
      const envelope = repo.read()!;
      expect(envelope.schema_version).toBe(DEMO_WORKSPACE_SCHEMA_VERSION);
    });

    it("stores identity anchors from metadata", () => {
      repo.ensure(baseMetadata());
      const envelope = repo.read()!;
      expect(envelope.tenant_id).toBe("demo-tenant-1");
      expect(envelope.source_name).toBe("Test Demo");
      expect(envelope.plan).toBe("starter");
      expect(envelope.activated_at).toBe("2026-07-01T00:00:00Z");
      expect(envelope.expires_at).toBe("2026-08-01T00:00:00Z");
    });

    it("includes plan_specific and tour_state fields", () => {
      repo.ensure(baseMetadata());
      const envelope = repo.read()!;
      expect(envelope).toHaveProperty("plan_specific");
      expect(envelope).toHaveProperty("tour_state");
    });

    it("sets a baseline_version on creation", () => {
      repo.ensure(baseMetadata());
      const envelope = repo.read()!;
      expect(envelope.baseline_version).toBeGreaterThanOrEqual(1);
    });

    it("sets saved_at from the current clock", () => {
      vi.useFakeTimers();
      vi.setSystemTime(new Date("2026-07-25T12:34:56.000Z"));

      repo.ensure(baseMetadata());

      expect(repo.read()!.saved_at).toBe("2026-07-25T12:34:56.000Z");
    });

    it("rejects a stored envelope with a mismatched tenant id", () => {
      const badKey = `${DEMO_WORKSPACE_KEY_PREFIX}${TENANT_ID}`;
      const badEnvelope: DemoWorkspaceEnvelope = {
        schema_version: DEMO_WORKSPACE_SCHEMA_VERSION,
        tenant_id: "different-tenant",
        source_name: "Bad",
        plan: "starter",
        activated_at: null,
        expires_at: null,
        baseline_version: 1,
        plan_specific: {},
        tour_state: {},
        saved_at: new Date().toISOString(),
      };
      storage.setItem(badKey, JSON.stringify(badEnvelope));

      expect(repo.read()).toBeNull();
    });

    it("rejects a stored envelope with old schema version", () => {
      const oldKey = `${DEMO_WORKSPACE_KEY_PREFIX}${TENANT_ID}`;
      const oldEnvelope = {
        schema_version: 1,
        tenant_id: TENANT_ID,
        source_name: "Old",
        plan: "starter" as const,
        activated_at: null,
        expires_at: null,
        baseline_version: 1,
        plan_specific: {},
        tour_state: {},
        saved_at: new Date().toISOString(),
      };
      storage.setItem(oldKey, JSON.stringify(oldEnvelope));

      expect(repo.read()).toMatchObject({
        schema_version: DEMO_WORKSPACE_SCHEMA_VERSION,
        tenant_id: TENANT_ID,
        baseline_version: 1,
      });
    });
  });

  describe("hydration (ensure)", () => {
    it("returns the existing envelope when workspace exists", () => {
      repo.ensure(baseMetadata());
      const envelope = repo.read()!;

      const second = repo.ensure(baseMetadata());
      expect(second.saved_at).toBe(envelope.saved_at);
    });

    it("invokes the baseline factory when no workspace exists", () => {
      const baseline: PlanBaselineFactory = vi.fn((plan) => ({
        plan_specific: { seeded: true, plan },
        tour_state: { toursCompleted: [] },
        baseline_version: 2,
      }));

      repo.ensure(baseMetadata(), baseline);

      expect(baseline).toHaveBeenCalledTimes(1);
      expect(baseline).toHaveBeenCalledWith("starter", baseMetadata());

      const envelope = repo.read()!;
      expect(envelope.plan_specific).toEqual({ seeded: true, plan: "starter" });
      expect(envelope.tour_state).toEqual({ toursCompleted: [] });
      expect(envelope.baseline_version).toBe(2);
    });

    it("does not invoke the baseline factory when workspace already exists", () => {
      repo.ensure(baseMetadata());
      const baseline: PlanBaselineFactory = vi.fn(() => ({
        plan_specific: {},
        tour_state: {},
        baseline_version: 1,
      }));

      repo.ensure(baseMetadata(), baseline);
      expect(baseline).not.toHaveBeenCalled();
    });

    it("uses a default empty baseline when no factory is provided", () => {
      repo.ensure(baseMetadata());
      const envelope = repo.read()!;
      expect(envelope.plan_specific).toEqual({});
      expect(envelope.tour_state).toEqual({});
      expect(envelope.baseline_version).toBe(1);
    });
  });

  describe("reset", () => {
    it("preserves lifecycle timestamps and credential context from metadata", () => {
      repo.ensure(baseMetadata());
      repo.saveTourState({ introDone: true });

      const updatedMeta = baseMetadata({
        activatedAt: "2026-07-01T00:00:00Z",
        expiresAt: "2026-08-01T00:00:00Z",
        credentialVersion: 1,
      });
      repo.reset(updatedMeta);
      const after = repo.read()!;

      expect(after.activated_at).toBe("2026-07-01T00:00:00Z");
      expect(after.expires_at).toBe("2026-08-01T00:00:00Z");
      expect(after.tour_state).toEqual({ introDone: true });
    });

    it("replaces plan_specific with fresh state", () => {
      repo.ensure(baseMetadata());
      const before = repo.read()!;

      repo.reset(baseMetadata());
      const after = repo.read()!;

      expect(after.plan_specific).toEqual({});
      expect(new Date(after.saved_at).getTime()).toBeGreaterThanOrEqual(
        new Date(before.saved_at).getTime(),
      );
    });

    it("accepts a baseline factory for plan-specific reset state", () => {
      repo.ensure(baseMetadata());
      const baseline: PlanBaselineFactory = vi.fn(() => ({
        plan_specific: { resetValue: true },
        tour_state: {},
        baseline_version: 3,
      }));

      repo.reset(baseMetadata(), baseline);
      const envelope = repo.read()!;
      expect(envelope.plan_specific).toEqual({ resetValue: true });
      expect(envelope.baseline_version).toBe(3);
    });

    it("preserves tour state across reset", () => {
      repo.ensure(baseMetadata());
      repo.saveTourState({ wizardCompleted: true, step: 5 });

      repo.reset(baseMetadata());
      const envelope = repo.read()!;
      expect(envelope.tour_state).toEqual({ wizardCompleted: true, step: 5 });
    });

    it("preserves tenant identity and plan", () => {
      repo.ensure(baseMetadata());
      repo.reset(proMetadata({ tenantId: "demo-tenant-1", plan: "pro" }));
      const envelope = repo.read()!;
      expect(envelope.tenant_id).toBe("demo-tenant-1");
      expect(envelope.source_name).toBe("Test Demo");
      expect(envelope.plan).toBe("pro");
    });
  });

  describe("logout / reload persistence", () => {
    it("workspace survives when only token data is cleared (logout)", () => {
      repo.ensure(baseMetadata());
      expect(repo.read()).not.toBeNull();

      // Simulate what logout does — clearTokenData leaves workspace untouched
      expect(repo.read()).not.toBeNull();
    });

    it("clearDemoWorkspace removes the stored workspace", () => {
      repo.ensure(baseMetadata());
      expect(repo.read()).not.toBeNull();

      clearDemoWorkspace(TENANT_ID, storage);
      expect(repo.read()).toBeNull();
    });

    it("clearDemoWorkspace for one tenant does not affect another", () => {
      const repoA = createDemoWorkspaceRepository("tenant-a", storage);
      const repoB = createDemoWorkspaceRepository("tenant-b", storage);

      repoA.ensure(baseMetadata({ tenantId: "tenant-a" }));
      repoB.ensure(baseMetadata({ tenantId: "tenant-b" }));

      clearDemoWorkspace("tenant-a", storage);

      expect(repoA.read()).toBeNull();
      expect(repoB.read()).not.toBeNull();
    });
  });

  describe("read returns null for missing or corrupted data", () => {
    it("returns null when no data in storage", () => {
      expect(repo.read()).toBeNull();
    });

    it("returns null on JSON parse error", () => {
      storage.setItem(repo.key, "not-json");
      expect(repo.read()).toBeNull();
    });

    it("returns null on schema version mismatch", () => {
      const bad = {
        schema_version: 999,
        tenant_id: TENANT_ID,
        source_name: "X",
        plan: "starter",
        activated_at: null,
        expires_at: null,
        baseline_version: 1,
        plan_specific: {},
        tour_state: {},
        saved_at: new Date().toISOString(),
      };
      storage.setItem(repo.key, JSON.stringify(bad));
      expect(repo.read()).toBeNull();
    });
  });

  describe("migration and recovery", () => {
    it("migrates a known version without losing lifecycle, business, or tour state", () => {
      storage.setItem(repo.key, JSON.stringify({
        schema_version: 1,
        tenant_id: TENANT_ID,
        source_name: "Migrated Demo",
        plan: "starter",
        activated_at: "2026-07-01T00:00:00.000Z",
        expires_at: "2026-08-01T00:00:00.000Z",
        plan_specific: { preserved: true },
        tour_state: { completed: true },
        saved_at: "2026-07-25T12:00:00.000Z",
      }));

      const migrated = repo.read();

      expect(migrated).toMatchObject({
        schema_version: DEMO_WORKSPACE_SCHEMA_VERSION,
        tenant_id: TENANT_ID,
        source_name: "Migrated Demo",
        plan: "starter",
        activated_at: "2026-07-01T00:00:00.000Z",
        expires_at: "2026-08-01T00:00:00.000Z",
        plan_specific: { preserved: true },
        tour_state: { completed: true },
        baseline_version: 1,
      });
      expect(JSON.parse(storage.getItem(repo.key)!)).toHaveProperty(
        "schema_version",
        DEMO_WORKSPACE_SCHEMA_VERSION,
      );
    });

    it("migrates schema version 2 pro workspace adding icon: null to Services", () => {
      const proServices = [
        { id: "svc-1", tenant_id: TENANT_ID, name: "Netflix", created_at: "2026-07-01T00:00:00Z", updated_at: "2026-07-01T00:00:00Z" },
        { id: "svc-2", tenant_id: TENANT_ID, name: "Disney+", created_at: "2026-07-01T00:00:00Z", updated_at: "2026-07-01T00:00:00Z" },
      ];
      storage.setItem(repo.key, JSON.stringify({
        schema_version: 2,
        tenant_id: TENANT_ID,
        source_name: "Pro Demo",
        plan: "pro",
        activated_at: "2026-07-01T00:00:00.000Z",
        expires_at: "2026-08-01T00:00:00.000Z",
        baseline_version: 2,
        plan_specific: {
          clients: [
            { id: "c-1", tenant_id: TENANT_ID, full_name: "Test Client", username: "test_client", phone: "1234567890", is_active: true, owner_user_id: "owner-1", created_at: "2026-07-01T00:00:00Z", updated_at: "2026-07-01T00:00:00Z" },
          ],
          services: proServices,
          plans: [
            { id: "p-1", tenant_id: TENANT_ID, service_id: "svc-1", name: "Básico", created_at: "2026-07-01T00:00:00Z", updated_at: "2026-07-01T00:00:00Z" },
          ],
          subscriptions: [],
          profile: { business_name: "Test", locale: "en", email: null, phone: null },
          integrations: { mailbox: { status: "connected", simulated: true }, whatsapp: { status: "connected", simulated: true } },
          code_services: [{ id: "disney", name: "Disney+", enabled: true }],
          blocked_identities: [{ id: "b-1", phone: "12025550101" }],
        },
        tour_state: { completed: true },
        saved_at: "2026-07-25T12:00:00.000Z",
      }));

      const migrated = repo.read();

      expect(migrated?.schema_version).toBe(3);
      expect((migrated?.plan_specific.services as Array<Record<string, unknown>>)[0].icon).toBeNull();
      expect(migrated?.tour_state).toEqual({ completed: true });
    });

    it("rejects a current-version pro workspace with services missing icon", () => {
      storage.setItem(repo.key, JSON.stringify({
        schema_version: DEMO_WORKSPACE_SCHEMA_VERSION,
        tenant_id: TENANT_ID,
        source_name: "Missing Icon",
        plan: "pro",
        activated_at: "2026-07-01T00:00:00.000Z",
        expires_at: "2026-08-01T00:00:00.000Z",
        baseline_version: 2,
        plan_specific: {
          clients: [
            { id: "c-1", tenant_id: TENANT_ID, full_name: "Test Client", username: "test_client", phone: "1234567890", is_active: true, owner_user_id: "owner-1", created_at: "2026-07-01T00:00:00Z", updated_at: "2026-07-01T00:00:00Z" },
          ],
          services: [
            { id: "svc-1", tenant_id: TENANT_ID, name: "Netflix", created_at: "2026-07-01T00:00:00Z", updated_at: "2026-07-01T00:00:00Z" },
          ],
          plans: [
            { id: "p-1", tenant_id: TENANT_ID, service_id: "svc-1", name: "Basic", created_at: "2026-07-01T00:00:00Z", updated_at: "2026-07-01T00:00:00Z" },
          ],
          subscriptions: [],
          profile: { business_name: "Test", locale: "en", email: null, phone: null },
          integrations: { mailbox: { status: "connected", simulated: true }, whatsapp: { status: "connected", simulated: true } },
          code_services: [{ id: "disney", name: "Disney+", enabled: true }],
          blocked_identities: [{ id: "b-1", phone: "12025550101" }],
        },
        tour_state: {},
        saved_at: "2026-07-25T12:00:00.000Z",
      }));

      expect(repo.read()).toBeNull();
    });

    it("recovers incompatible data to the authenticated plan without merging plans", () => {
      storage.setItem(repo.key, JSON.stringify({
        schema_version: DEMO_WORKSPACE_SCHEMA_VERSION,
        tenant_id: TENANT_ID,
        source_name: "Wrong Plan",
        plan: "pro",
        activated_at: baseMetadata().activatedAt,
        expires_at: baseMetadata().expiresAt,
        baseline_version: 2,
        plan_specific: { proOnly: true },
        tour_state: { completed: true },
        saved_at: baseMetadata().serverTime,
      }));
      const baseline = baselineFactory({ starterOnly: true });

      const recovered = repo.ensure(baseMetadata(), baseline);

      expect(recovered.plan).toBe("starter");
      expect(recovered.plan_specific).toEqual({ starterOnly: true });
      expect(recovered.plan_specific).not.toHaveProperty("proOnly");
      expect(recovered.tour_state).toEqual({ baselineTour: false });
      expect(repo.consumeRecoveryNotice()).toMatchObject({ kind: "reset" });
      expect(repo.consumeRecoveryNotice()).toBeNull();
    });

    it("recovers impossible timestamps and malformed state to a fresh baseline", () => {
      storage.setItem(repo.key, JSON.stringify({
        schema_version: DEMO_WORKSPACE_SCHEMA_VERSION,
        tenant_id: TENANT_ID,
        source_name: "Broken Demo",
        plan: "starter",
        activated_at: "2026-08-02T00:00:00.000Z",
        expires_at: "2026-08-01T00:00:00.000Z",
        baseline_version: 2,
        plan_specific: [],
        tour_state: {},
        saved_at: "not-a-timestamp",
      }));
      const baseline = baselineFactory({ recovered: true });

      const recovered = repo.ensure(baseMetadata(), baseline);

      expect(recovered.plan_specific).toEqual({ recovered: true });
      expect(repo.consumeRecoveryNotice()).toEqual({ kind: "reset" });
      expect(repo.consumeRecoveryNotice()).toBeNull();
    });

    it("removes expired orphan keys during bootstrap without hydrating their contents", () => {
      const orphanKey = `${DEMO_WORKSPACE_KEY_PREFIX}orphan-tenant`;
      storage.setItem(orphanKey, JSON.stringify({
        schema_version: DEMO_WORKSPACE_SCHEMA_VERSION,
        tenant_id: "orphan-tenant",
        source_name: "Expired Orphan",
        plan: "pro",
        activated_at: "2026-07-01T00:00:00.000Z",
        expires_at: "2026-07-20T00:00:00.000Z",
        baseline_version: 2,
        plan_specific: {},
        tour_state: {},
        saved_at: "2026-07-20T00:00:00.000Z",
      }));

      repo.ensure(baseMetadata({ serverTime: "2026-07-25T12:00:00.000Z" }), baselineFactory({ fresh: true }));

      expect(storage.getItem(orphanKey)).toBeNull();
    });

    it("removes an expired orphan before creating the current plan baseline", () => {
      storage.setItem(repo.key, JSON.stringify({
        schema_version: DEMO_WORKSPACE_SCHEMA_VERSION,
        tenant_id: TENANT_ID,
        source_name: "Expired Demo",
        plan: "starter",
        activated_at: "2026-07-01T00:00:00.000Z",
        expires_at: "2026-07-20T00:00:00.000Z",
        baseline_version: 2,
        plan_specific: { stale: true },
        tour_state: {},
        saved_at: "2026-07-20T00:00:00.000Z",
      }));
      const baseline = baselineFactory({ fresh: true });

      const recovered = repo.ensure(baseMetadata({ serverTime: "2026-07-25T12:00:00.000Z" }), baseline);

      expect(recovered.plan_specific).toEqual({ fresh: true });
      expect(repo.read()?.plan_specific).toEqual({ fresh: true });
    });
  });

  describe("storage failures", () => {
    it("exposes unavailable storage and never falls back to another persistence boundary", () => {
      const unavailableStorage: Storage = {
        get length() {
          return 0;
        },
        clear: () => undefined,
        getItem: () => {
          throw new DOMException("Blocked", "SecurityError");
        },
        key: () => null,
        removeItem: () => undefined,
        setItem: () => {
          throw new DOMException("Blocked", "SecurityError");
        },
      };
      const unavailableRepo = createDemoWorkspaceRepository("blocked-demo", unavailableStorage);

      expect(unavailableRepo.storageState()).toBe("unavailable");
      expect(() => unavailableRepo.ensure(baseMetadata({ tenantId: "blocked-demo" }), baselineFactory({ value: true }))).toThrow(
        "demo_workspace_storage_unavailable",
      );
    });

    it("classifies quota failures explicitly", () => {
      const quotaStorage: Storage = {
        get length() {
          return 0;
        },
        clear: () => undefined,
        getItem: () => null,
        key: () => null,
        removeItem: () => undefined,
        setItem: () => {
          throw new DOMException("Full", "QuotaExceededError");
        },
      };
      const quotaRepo = createDemoWorkspaceRepository("quota-demo", quotaStorage);

      expect(() => quotaRepo.ensure(baseMetadata({ tenantId: "quota-demo" }), baselineFactory({ value: true }))).toThrow(
        "demo_workspace_quota_exceeded",
      );
      expect(quotaRepo.storageState()).toBe("quota_exceeded");
    });
  });

  describe("saveTourState", () => {
    it("merges tour state into existing envelope", () => {
      repo.ensure(baseMetadata());
      repo.saveTourState({ step: "intro" });

      const envelope = repo.read()!;
      expect(envelope.tour_state).toEqual({ step: "intro" });
    });

    it("preserves existing tour state on partial update", () => {
      repo.ensure(baseMetadata());
      repo.saveTourState({ step1: true });
      repo.saveTourState({ step2: true });

      const envelope = repo.read()!;
      expect(envelope.tour_state).toEqual({ step1: true, step2: true });
    });

    it("does not affect plan_specific", () => {
      repo.ensure(baseMetadata());
      repo.saveTourState({ done: true });

      const envelope = repo.read()!;
      expect(envelope.plan_specific).toEqual({});
    });
  });

  describe("baseline seam", () => {
    it("starter vs pro baseline can differ", () => {
      const starterBaseline: PlanBaselineFactory = vi.fn(() => ({
        plan_specific: { widgetCount: 5 },
        tour_state: { starterTour: false },
        baseline_version: 1,
      }));
      const proBaseline: PlanBaselineFactory = vi.fn(() => ({
        plan_specific: { widgetCount: 100, advancedFeature: true },
        tour_state: { proTour: false },
        baseline_version: 2,
      }));

      const starterRepo = createDemoWorkspaceRepository("tenant-starter", storage);
      starterRepo.ensure(baseMetadata({ tenantId: "tenant-starter", plan: "starter" }), starterBaseline);

      const proRepo = createDemoWorkspaceRepository("tenant-pro", storage);
      proRepo.ensure(proMetadata({ tenantId: "tenant-pro" }), proBaseline);

      expect(starterRepo.read()!.plan_specific).toEqual({ widgetCount: 5 });
      expect(proRepo.read()!.plan_specific).toEqual({ widgetCount: 100, advancedFeature: true });
    });

    it("baseline factory receives the correct plan and metadata", () => {
      const factory: PlanBaselineFactory = vi.fn(() => ({
        plan_specific: {},
        tour_state: {},
        baseline_version: 1,
      }));

      const meta = baseMetadata({ tenantId: TENANT_ID, plan: "pro" });
      repo.ensure(meta, factory);

      expect(factory).toHaveBeenCalledWith("pro", meta);
    });
  });

  describe("privacy", () => {
    it("does not emit workspace values to console telemetry", () => {
      const logSpy = vi.spyOn(console, "log").mockImplementation(() => undefined);
      const warnSpy = vi.spyOn(console, "warn").mockImplementation(() => undefined);
      const errorSpy = vi.spyOn(console, "error").mockImplementation(() => undefined);
      const privateValue = "private-workspace-value";

      repo.ensure(baseMetadata(), baselineFactory({ business_name: privateValue }));

      expect(logSpy).not.toHaveBeenCalled();
      expect(warnSpy).not.toHaveBeenCalled();
      expect(errorSpy).not.toHaveBeenCalled();
      expect(JSON.stringify([...logSpy.mock.calls, ...warnSpy.mock.calls, ...errorSpy.mock.calls])).not.toContain(privateValue);
      logSpy.mockRestore();
      warnSpy.mockRestore();
      errorSpy.mockRestore();
    });
  });

  describe("no business HTTP calls", () => {
    it("read does not make HTTP requests", () => {
      repo.ensure(baseMetadata());
      fetchSpy.mockClear();

      repo.read();
      expect(fetchSpy).not.toHaveBeenCalled();
    });

    it("ensure does not make HTTP requests when workspace exists", () => {
      repo.ensure(baseMetadata());
      fetchSpy.mockClear();

      repo.ensure(baseMetadata());
      expect(fetchSpy).not.toHaveBeenCalled();
    });

    it("ensure does not make HTTP requests when creating new workspace", () => {
      fetchSpy.mockClear();

      repo.ensure(baseMetadata());
      expect(fetchSpy).not.toHaveBeenCalled();
    });

    it("reset does not make HTTP requests", () => {
      repo.ensure(baseMetadata());
      fetchSpy.mockClear();

      repo.reset(baseMetadata());
      expect(fetchSpy).not.toHaveBeenCalled();
    });

    it("saveTourState does not make HTTP requests", () => {
      repo.ensure(baseMetadata());
      fetchSpy.mockClear();

      repo.saveTourState({ step: "test" });
      expect(fetchSpy).not.toHaveBeenCalled();
    });

    it("clearDemoWorkspace does not make HTTP requests", () => {
      repo.ensure(baseMetadata());
      fetchSpy.mockClear();

      clearDemoWorkspace(TENANT_ID, storage);
      expect(fetchSpy).not.toHaveBeenCalled();
    });
  });
});
