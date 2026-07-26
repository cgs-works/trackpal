import type { DemoAuthMetadata } from "@/store/auth";
import type { PlanBaselineFactory } from "./demo-workspace";

export const DEMO_BASELINE_VERSION = 1;

export interface DemoCodeService {
  id: string;
  name: string;
  enabled: boolean;
}

export interface DemoBlockedIdentity {
  id: string;
  phone: string;
}

export interface StarterDemoWorkspaceState {
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

export const createDemoBaseline: PlanBaselineFactory = (plan, metadata) => ({
  plan_specific: plan === "starter" ? createStarterState(metadata) : {},
  tour_state: {},
  baseline_version: DEMO_BASELINE_VERSION,
});

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
