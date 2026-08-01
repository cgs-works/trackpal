import type { Service, Plan } from "@/features/admin/services/catalog-api";
import type { DemoAuthMetadata } from "@/store/auth";
import type { Client } from "@/features/admin/services/client-api";
import type { Subscription } from "@/features/admin/services/subscription-api";
import type { ReminderSettings } from "@/features/admin/services/reminder-api";
import type { TenantSettings } from "@/features/admin/services/settings-api";
import type { PlanBaselineFactory } from "./demo-workspace";

export const DEMO_BASELINE_VERSION = 3;

export interface DemoCodeService {
  id: string;
  name: string;
  enabled: boolean;
}

export interface DemoBlockedIdentity {
  id: string;
  phone: string;
}

export interface DemoSubscriptionRelation extends Omit<Subscription, "has_password" | "has_pin"> {
  streaming_secret?: string | null;
  pin_secret?: string | null;
}

export interface DemoWorkspaceState {
  profile: {
    business_name: string;
    locale: "en" | "es";
    email?: string | null;
    phone?: string | null;
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
  reminder_settings?: ReminderSettings;
  tenant_settings?: TenantSettings;
  clients?: Client[];
  services?: Service[];
  plans?: Plan[];
  subscriptions?: DemoSubscriptionRelation[];
}

export type StarterDemoWorkspaceState = Omit<DemoWorkspaceState, "clients" | "services" | "plans" | "subscriptions">;
export interface ProDemoWorkspaceState extends DemoWorkspaceState {
  clients: Client[];
  services: Service[];
  plans: Plan[];
  subscriptions: DemoSubscriptionRelation[];
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
      email: null,
      phone: null,
    },
    integrations: {
      mailbox: { status: "connected", simulated: true },
      whatsapp: { status: "connected", simulated: true },
    },
    code_services: [
      { id: "disney", name: "Disney+", enabled: true },
      { id: "hbo_max", name: "HBO Max", enabled: true },
      { id: "netflix", name: "Netflix", enabled: true },
      { id: "prime_video", name: "Prime Video", enabled: true },
      { id: "spotify", name: "Spotify", enabled: true },
      { id: "universal_plus", name: "Universal+", enabled: true },
    ],
    blocked_identities: [
      { id: "blocked-1", phone: "12025550101" },
      { id: "blocked-2", phone: "12025550102" },
    ],
    reminder_settings: {
      id: `reminders-${metadata.tenantId}`,
      tenant_id: metadata.tenantId,
      warning_days: [7, 3, 1],
      reminder_time: "09:00",
      recipient_mode: "tenant_only",
      reminders_enabled: false,
      custom_message_tenant: null,
      custom_message_client: null,
      created_at: metadata.serverTime,
      updated_at: metadata.serverTime,
    },
    tenant_settings: {
      tenant_id: metadata.tenantId,
      locale: "en",
      timezone: "UTC",
      country: null,
      currency: null,
      created_at: metadata.serverTime,
      updated_at: metadata.serverTime,
    },
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

function createProSubscriptions(metadata: DemoAuthMetadata, clients: Client[], services: Service[], plans: Plan[]): DemoSubscriptionRelation[] {
  const serviceByKey = new Map(
    services.map((service) => [service.id.split("-").slice(-1)[0], service]),
  );
  const planByKey = new Map(plans.map((plan) => [plan.name.toLowerCase(), plan]));
  const client = (index: number) => clients[index].id;
  const service = (key: string) => serviceByKey.get(key)!;
  const plan = (name: string, serviceKey: string) => {
    const selected = plans.find(
      (item) => item.service_id === service(serviceKey).id && item.name.toLowerCase() === name.toLowerCase(),
    );
    return selected ?? planByKey.get(name.toLowerCase())!;
  };
  const origin = metadata.activatedAt ?? metadata.serverTime;
  const at = (days: number) => new Date(new Date(origin).getTime() + days * 86_400_000).toISOString();
  const now = at(0);
  const build = (
    id: string,
    clientIndex: number,
    serviceKey: string,
    planName: string,
    email: string,
    startsAt: number,
    expiresAt: number,
    durationType: string,
    status: DemoSubscriptionRelation["status"],
    password: string,
    profileName?: string,
    profilePin?: string,
    cancelledAt?: number,
  ): DemoSubscriptionRelation => ({
    id: `${metadata.tenantId}-${id}`,
    tenant_id: metadata.tenantId,
    client_id: client(clientIndex),
    service_id: service(serviceKey).id,
    plan_id: plan(planName, serviceKey).id,
    streaming_email: email,
    streaming_secret: password,
    profile_name: profileName ?? null,
    pin_secret: profilePin ?? null,
    duration_type: durationType,
    starts_at: at(startsAt),
    expires_at: at(expiresAt),
    cancelled_at: cancelledAt === undefined ? null : at(cancelledAt),
    status,
    created_at: now,
    updated_at: now,
  });

  return [
    build("subscription-active", 0, "netflix", "Básico", "demo.active@example.test", -14, 16, "1_month", "active", "demo-active-secret"),
    build("subscription-expiring-7", 1, "disney", "Premium", "demo.expiring.7@example.test", -23, 7, "1_month", "active", "demo-expiring-7-secret", "Perfil Demo 7", "7007"),
    build("subscription-expiring-3", 2, "hbo_max", "Básico", "demo.expiring.3@example.test", -27, 3, "1_month", "active", "demo-expiring-3-secret"),
    build("subscription-expiring-1", 3, "prime_video", "Premium", "demo.expiring.1@example.test", -29, 1, "1_month", "active", "demo-expiring-1-secret", "Perfil Demo 1", "1001"),
    build("subscription-renewed", 0, "spotify", "Individual", "demo.renewed@example.test", -5, 25, "3_months", "active", "demo-renewed-secret"),
    build("subscription-expired", 0, "universal_plus", "Básico", "demo.expired@example.test", -45, -15, "1_month", "expired", "demo-expired-secret"),
    build("subscription-cancelled", 1, "netflix", "Básico", "demo.cancelled@example.test", -20, 10, "1_month", "cancelled", "demo-cancelled-secret", undefined, undefined, -10),
    build("subscription-reactivated", 2, "disney", "Básico", "demo.reactivated@example.test", -8, 22, "1_month", "cancelled", "demo-reactivated-secret", "Perfil Reactivado", "2222", -2),
  ];
}

const serviceDefinitions: Array<[string, string, string]> = [
  ["service-disney", "Disney+", "tabler:brand-disney"],
  ["service-hbo_max", "HBO Max", "simple-icons:max"],
  ["service-netflix", "Netflix", "simple-icons:netflix"],
  ["service-prime_video", "Prime Video", "simple-icons:primevideo"],
  ["service-spotify", "Spotify", "simple-icons:spotify"],
  ["service-universal_plus", "Universal+", "mdi:television-play"],
];

export const createDemoBaseline: PlanBaselineFactory = (plan, metadata) => {
  const starter = createStarterState(metadata);
  if (plan === "starter") {
    return {
      plan_specific: starter,
      tour_state: {},
      baseline_version: DEMO_BASELINE_VERSION,
    };
  }

  const now = metadata.serverTime;
  const services: Service[] = serviceDefinitions.map(([id, name, icon]) => ({
    id: `${metadata.tenantId}-${id}`,
    tenant_id: metadata.tenantId,
    name,
    icon,
    created_at: now,
    updated_at: now,
  }));
  const planDefinitions: Array<[string, string, string, string | null]> = [
    ["service-disney", "disney-basic", "Básico", null],
    ["service-disney", "disney-premium", "Premium", "25.00"],
    ["service-hbo_max", "hbo-basic", "Básico", null],
    ["service-hbo_max", "hbo-premium", "Premium", "22.00"],
    ["service-netflix", "netflix-basic", "Básico", "8.50"],
    ["service-netflix", "netflix-premium", "Premium HD", "18.00"],
    ["service-prime_video", "prime-basic", "Básico", null],
    ["service-prime_video", "prime-premium", "Premium", "15.00"],
    ["service-spotify", "spotify-individual", "Individual", "9.99"],
    ["service-spotify", "spotify-family", "Familiar", "16.99"],
    ["service-universal_plus", "universal-basic", "Básico", null],
    ["service-universal_plus", "universal-premium", "Premium", "12.00"],
  ];
  const plans: Plan[] = planDefinitions.map(([serviceKey, planKey, name, price]) => ({
    id: `${metadata.tenantId}-${planKey}`,
    tenant_id: metadata.tenantId,
    service_id: `${metadata.tenantId}-${serviceKey}`,
    name,
    price,
    created_at: now,
    updated_at: now,
  }));
  const clients = createProClients(metadata);

  return {
    plan_specific: {
      ...starter,
      clients,
      services,
      plans,
      subscriptions: createProSubscriptions(metadata, clients, services, plans),
    },
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
  if (
    !state ||
    !Array.isArray(state.clients) ||
    !Array.isArray(state.services) ||
    !Array.isArray(state.plans) ||
    !Array.isArray(state.subscriptions)
  ) return null;
  return state;
}
