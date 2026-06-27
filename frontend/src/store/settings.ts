import { create } from "zustand";
import {
  getReminderSettings,
  updateReminderSettings as apiUpdateReminderSettings,
  type ReminderSettings,
  type ReminderSettingsUpdate,
} from "@/features/admin/services/reminder-api";
import {
  getTenantSettings,
  updateTenantSettings as apiUpdateTenantSettings,
  getTimezones,
  getMailbox as apiGetMailbox,
  getPublicApiKey as apiGetPublicApiKey,
  savePublicApiKeyOrigins as apiSavePublicApiKeyOrigins,
  regeneratePublicApiKey as apiRegeneratePublicApiKey,
  revokePublicApiKey as apiRevokePublicApiKey,
  type TenantSettings,
  type TenantSettingsUpdate,
  type TimezoneOption,
  type Mailbox,
  type PublicApiKeyConfig,
} from "@/features/admin/services/settings-api";

interface ApiError {
  response?: { data?: { detail?: string | Array<{ msg?: string }> } };
}

interface SettingsState {
  reminderSettings: ReminderSettings | null;
  tenantSettings: TenantSettings | null;
  timezoneOptions: TimezoneOption[];
  mailbox: Mailbox | null;
  publicApiKey: PublicApiKeyConfig | null;
  reminderSettingsLoaded: boolean;
  tenantSettingsLoaded: boolean;
  timezonesLoaded: boolean;
  mailboxLoaded: boolean;
  publicApiKeyLoaded: boolean;
  reminderSettingsInFlight: Promise<ReminderSettings | null> | null;
  tenantSettingsInFlight: Promise<TenantSettings | null> | null;
  timezonesInFlight: Promise<TimezoneOption[]> | null;
  mailboxInFlight: Promise<Mailbox | null> | null;
  publicApiKeyInFlight: Promise<PublicApiKeyConfig | null> | null;
  settingsLoadError: string | null;
  _settingsEpoch: number;

  loadReminderSettings: () => Promise<ReminderSettings | null>;
  loadTenantSettings: () => Promise<TenantSettings | null>;
  loadTimezoneOptions: () => Promise<TimezoneOption[]>;
  loadMailbox: () => Promise<Mailbox | null>;
  loadPublicApiKey: () => Promise<PublicApiKeyConfig | null>;
  updateReminderSettings: (
    settings: ReminderSettingsUpdate,
  ) => Promise<ReminderSettings>;
  updateTenantSettings: (
    settings: TenantSettingsUpdate,
  ) => Promise<TenantSettings>;
  savePublicApiKeyOrigins: (
    origins: string[],
  ) => Promise<PublicApiKeyConfig>;
  regeneratePublicApiKey: () => Promise<PublicApiKeyConfig>;
  revokePublicApiKey: () => Promise<void>;
  clearSettingsCache: () => void;
}

export const useSettingsStore = create<SettingsState>((set, get) => ({
  reminderSettings: null,
  tenantSettings: null,
  timezoneOptions: [],
  mailbox: null,
  publicApiKey: null,
  reminderSettingsLoaded: false,
  tenantSettingsLoaded: false,
  timezonesLoaded: false,
  mailboxLoaded: false,
  publicApiKeyLoaded: false,
  reminderSettingsInFlight: null,
  tenantSettingsInFlight: null,
  timezonesInFlight: null,
  mailboxInFlight: null,
  publicApiKeyInFlight: null,
  settingsLoadError: null,
  _settingsEpoch: 0,

  loadReminderSettings: async () => {
    const state = get();
    if (state.reminderSettingsLoaded) return state.reminderSettings;
    const promise =
      state.reminderSettingsInFlight || loadReminderSettings(set, get);
    if (!state.reminderSettingsInFlight) {
      set({ reminderSettingsInFlight: promise });
    }
    return promise;
  },

  loadTenantSettings: async () => {
    const state = get();
    if (state.tenantSettingsLoaded) return state.tenantSettings;
    const promise =
      state.tenantSettingsInFlight || loadTenantSettings(set, get);
    if (!state.tenantSettingsInFlight) {
      set({ tenantSettingsInFlight: promise });
    }
    return promise;
  },

  loadTimezoneOptions: async () => {
    const state = get();
    if (state.timezonesLoaded) return state.timezoneOptions;
    const promise = state.timezonesInFlight || loadTimezones(set, get);
    if (!state.timezonesInFlight) {
      set({ timezonesInFlight: promise });
    }
    return promise;
  },

  loadMailbox: async () => {
    const state = get();
    if (state.mailboxLoaded) return state.mailbox;
    const promise = state.mailboxInFlight || loadMailbox(set, get);
    if (!state.mailboxInFlight) {
      set({ mailboxInFlight: promise });
    }
    return promise;
  },

  loadPublicApiKey: async () => {
    const state = get();
    if (state.publicApiKeyLoaded) return state.publicApiKey;
    const promise =
      state.publicApiKeyInFlight || loadPublicApiKey(set, get);
    if (!state.publicApiKeyInFlight) {
      set({ publicApiKeyInFlight: promise });
    }
    return promise;
  },

  updateReminderSettings: async (payload) => {
    const data = await apiUpdateReminderSettings(payload);
    set({ reminderSettings: data, reminderSettingsLoaded: true });
    return data;
  },

  updateTenantSettings: async (payload) => {
    const data = await apiUpdateTenantSettings(payload);
    set({ tenantSettings: data, tenantSettingsLoaded: true });
    return data;
  },

  savePublicApiKeyOrigins: async (origins) => {
    const data = await apiSavePublicApiKeyOrigins(origins);
    set({
      publicApiKey: data,
      publicApiKeyLoaded: true,
      publicApiKeyInFlight: null,
    });
    return data;
  },

  regeneratePublicApiKey: async () => {
    const data = await apiRegeneratePublicApiKey();
    set({
      publicApiKey: data,
      publicApiKeyLoaded: true,
      publicApiKeyInFlight: null,
    });
    return data;
  },

  revokePublicApiKey: async () => {
    await apiRevokePublicApiKey();
    set({
      publicApiKey: null,
      publicApiKeyLoaded: true,
      publicApiKeyInFlight: null,
    });
  },

  clearSettingsCache: () => {
    set({
      reminderSettings: null,
      tenantSettings: null,
      timezoneOptions: [],
      mailbox: null,
      publicApiKey: null,
      reminderSettingsLoaded: false,
      tenantSettingsLoaded: false,
      timezonesLoaded: false,
      mailboxLoaded: false,
      publicApiKeyLoaded: false,
      reminderSettingsInFlight: null,
      tenantSettingsInFlight: null,
      timezonesInFlight: null,
      mailboxInFlight: null,
      publicApiKeyInFlight: null,
      settingsLoadError: null,
      _settingsEpoch: get()._settingsEpoch + 1,
    });
  },
}));

function getErrorMessage(error: unknown, fallback: string): string {
  const detail = (error as ApiError)?.response?.data?.detail;
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail)) {
    return detail.map((item) => item.msg || "Unknown error").join("; ");
  }
  return fallback;
}

async function loadReminderSettings(
  set: (partial: Partial<SettingsState>) => void,
  get: () => SettingsState,
): Promise<ReminderSettings | null> {
  const epoch = get()._settingsEpoch;
  try {
    const data = await getReminderSettings();
    if (get()._settingsEpoch !== epoch) return null;
    set({
      reminderSettings: data,
      reminderSettingsLoaded: true,
      settingsLoadError: null,
      reminderSettingsInFlight: null,
    });
    return data;
  } catch (error: unknown) {
    set({
      settingsLoadError: getErrorMessage(error, "Failed to load reminder settings"),
      reminderSettingsInFlight: null,
    });
    throw error;
  }
}

async function loadTenantSettings(
  set: (partial: Partial<SettingsState>) => void,
  get: () => SettingsState,
): Promise<TenantSettings | null> {
  const epoch = get()._settingsEpoch;
  try {
    const data = await getTenantSettings();
    if (get()._settingsEpoch !== epoch) return null;
    set({
      tenantSettings: data,
      tenantSettingsLoaded: true,
      settingsLoadError: null,
      tenantSettingsInFlight: null,
    });
    return data;
  } catch (error: unknown) {
    set({
      settingsLoadError: getErrorMessage(error, "Failed to load tenant settings"),
      tenantSettingsInFlight: null,
    });
    throw error;
  }
}

async function loadTimezones(
  set: (partial: Partial<SettingsState>) => void,
  get: () => SettingsState,
): Promise<TimezoneOption[]> {
  const epoch = get()._settingsEpoch;
  try {
    const data = await getTimezones();
    if (get()._settingsEpoch !== epoch) return [];
    set({
      timezoneOptions: data,
      timezonesLoaded: true,
      timezonesInFlight: null,
    });
    return data;
  } catch (error) {
    console.warn("[settings] Failed to load timezone options:", error);
    set({
      timezoneOptions: [],
      timezonesLoaded: false,
      timezonesInFlight: null,
    });
    return [];
  }
}

async function loadMailbox(
  set: (partial: Partial<SettingsState>) => void,
  get: () => SettingsState,
): Promise<Mailbox | null> {
  const epoch = get()._settingsEpoch;
  try {
    const data = await apiGetMailbox();
    if (get()._settingsEpoch !== epoch) return null;
    set({
      mailbox: data,
      mailboxLoaded: true,
      mailboxInFlight: null,
    });
    return data;
  } catch (error) {
    console.warn("[settings] Failed to load mailbox:", error);
    set({
      mailbox: null,
      mailboxLoaded: false,
      mailboxInFlight: null,
    });
    return null;
  }
}

async function loadPublicApiKey(
  set: (partial: Partial<SettingsState>) => void,
  get: () => SettingsState,
): Promise<PublicApiKeyConfig | null> {
  const epoch = get()._settingsEpoch;
  try {
    const data = await apiGetPublicApiKey();
    if (get()._settingsEpoch !== epoch) return null;
    set({
      publicApiKey: data,
      publicApiKeyLoaded: true,
      publicApiKeyInFlight: null,
      settingsLoadError: null,
    });
    return data;
  } catch (error: unknown) {
    set({
      settingsLoadError: getErrorMessage(error, "Failed to load public API key"),
      publicApiKeyInFlight: null,
    });
    throw error;
  }
}
