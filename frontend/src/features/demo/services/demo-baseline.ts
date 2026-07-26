import type { DemoAuthMetadata } from "@/store/auth";
import type { Client } from "@/features/admin/services/client-api";
import type { PlanBaselineFactory } from "./demo-workspace";

export const DEMO_BASELINE_VERSION = 2;

export interface DemoCodeService {
  id: string;
  name: string;
  enabled: boolean;
}

export interface DemoBlockedIdentity {
  id: string;
  phone: string;
}

export interface DemoWorkspaceState {
  profile: {
    business_name: string;
    locale: "en" | "es";
  };
  integrations: {
    mailbox: {
      status: "connected";
      simulated: true;
    };
    whatsapp: {
      status: "connected";
      simulated: true;
    };
  };
  code_services: DemoCodeService[];
  blocked_identities: DemoBlockedIdentity[];
  clients?: Client[];
}

export type StarterDemoWorkspaceState = Omit<DemoWorkspaceState, "clients">;
export interface ProDemoWorkspaceState extends DemoWorkspaceState {
  clients: Client[];
}

function dateAtOffset(metadata: DemoAuthMetadata, days: number): string {
  const origin = metadata.activatedAt ?? metadata.serverTime;
  return new Date(new Date(origin).getTime() + days * 86_400_000).toISOString();
}

function createStarterState(metadata: DemoAuthMetadata): StarterDemoWorkspaceState {
  return {
    profile: {
      business_name: metadata.name,
      locale: "en",
    },
    integrations: {
      mailbox: { status: "connected", simulated: true },
      whatsapp: { status: "connected", simulated: true },
    },
    code_services: [
      { id: "secure-mail", name: "Secure Mail", enabled: true },
      { id: "account-access", name: "Account Access", enabled: true },
      { id: "verification-hub", name: "Verification Hub", enabled: true },
    ],
    blocked_identities: [
      { id: "blocked-1", phone: "12025550101" },
      { id: "blocked-2", phone: "12025550102" },
    ],
  };
}

function createProClients(metadata: DemoAuthMetadata): Client[] {
  const records = [
    ["Avery Stone", "avery_stone", "14155552671", true, -10],
    ["Mina Duarte", "mina_duarte", "14155552672", true, -7],
    ["Leo Chen", "leo_chen", "14155552673", true, -4],
    ["Priya Nair", "priya_nair", "14155552674", false, -2],
    ["Jon Bell", "jon_bell", "14155552675", false, -1],
  ] as const;

  return records.map(([fullName, username, phone, isActive, offset], index) => {
    const id = `client-${metadata.tenantId}-${index + 1}`;
    const timestamp = dateAtOffset(metadata, offset);
    return {
      id,
      tenant_id: metadata.tenantId,
      owner_user_id: `local-owner-${metadata.tenantId}-${index + 1}`,
      full_name: fullName,
      username: `demo_${username}`,
      phone,
      is_active: isActive,
      created_at: timestamp,
      updated_at: timestamp,
    };
  });
}

export const createDemoBaseline: PlanBaselineFactory = (plan, metadata) => {
  const starter = createStarterState(metadata);
  return {
    plan_specific:
      plan === "pro" ? { ...starter, clients: createProClients(metadata) } : starter,
    tour_state: {},
    baseline_version: DEMO_BASELINE_VERSION,
  };
};

export function readStarterDemoState(
  planSpecific: Record<string, unknown>,
): StarterDemoWorkspaceState | null {
  const state = planSpecific as Partial<StarterDemoWorkspaceState>;
  if (
    !state.profile ||
    typeof state.profile.business_name !== "string" ||
    (state.profile.locale !== "en" && state.profile.locale !== "es") ||
    !state.integrations ||
    !Array.isArray(state.code_services) ||
    !Array.isArray(state.blocked_identities)
  ) {
    return null;
  }
  return state as StarterDemoWorkspaceState;
}

export function readProDemoState(
  planSpecific: Record<string, unknown>,
): ProDemoWorkspaceState | null {
  const state = readStarterDemoState(planSpecific) as ProDemoWorkspaceState | null;
  if (!state || !Array.isArray(state.clients)) return null;
  return state;
}
