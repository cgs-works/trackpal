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
import type { SettingsDataSourceContract } from "@/lib/data-source";

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

  loadReminderSettings: (source?: SettingsDataSourceContract) => Promise<ReminderSettings | null>;
  loadTenantSettings: (source?: SettingsDataSourceContract) => Promise<TenantSettings | null>;
  loadTimezoneOptions: (source?: SettingsDataSourceContract) => Promise<TimezoneOption[]>;
  loadMailbox: (source?: SettingsDataSourceContract) => Promise<Mailbox | null>;
  loadPublicApiKey: (source?: SettingsDataSourceContract) => Promise<PublicApiKeyConfig | null>;
  updateReminderSettings: (
    settings: ReminderSettingsUpdate,
    source?: SettingsDataSourceContract,
  ) => Promise<ReminderSettings>;
  updateTenantSettings: (
    settings: TenantSettingsUpdate,
    source?: SettingsDataSourceContract,
  ) => Promise<TenantSettings>;
  savePublicApiKeyOrigins: (
    origins: string[],
    source?: SettingsDataSourceContract,
  ) => Promise<PublicApiKeyConfig>;
  regeneratePublicApiKey: (
    source?: SettingsDataSourceContract,
  ) => Promise<PublicApiKeyConfig>;
  revokePublicApiKey: (
    source?: SettingsDataSourceContract,
  ) => Promise<void>;
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

  loadReminderSettings: async (source) => {
    const state = get();
    if (state.reminderSettingsLoaded) return state.reminderSettings;
    const promise =
      state.reminderSettingsInFlight || loadReminderSettings(set, get, source);
    if (!state.reminderSettingsInFlight) {
      set({ reminderSettingsInFlight: promise });
    }
    return promise;
  },

  loadTenantSettings: async (source) => {
    const state = get();
    if (state.tenantSettingsLoaded) return state.tenantSettings;
    const promise =
      state.tenantSettingsInFlight || loadTenantSettings(set, get, source);
    if (!state.tenantSettingsInFlight) {
      set({ tenantSettingsInFlight: promise });
    }
    return promise;
  },

  loadTimezoneOptions: async (source) => {
    const state = get();
    if (state.timezonesLoaded) return state.timezoneOptions;
    const promise = state.timezonesInFlight || loadTimezones(set, get, source);
    if (!state.timezonesInFlight) {
      set({ timezonesInFlight: promise });
    }
    return promise;
  },

  loadMailbox: async (source) => {
    const state = get();
    if (state.mailboxLoaded) return state.mailbox;
    const promise = state.mailboxInFlight || loadMailbox(set, get, source);
    if (!state.mailboxInFlight) {
      set({ mailboxInFlight: promise });
    }
    return promise;
  },

  loadPublicApiKey: async (source) => {
    const state = get();
    if (state.publicApiKeyLoaded) return state.publicApiKey;
    const promise =
      state.publicApiKeyInFlight || loadPublicApiKey(set, get, source);
    if (!state.publicApiKeyInFlight) {
      set({ publicApiKeyInFlight: promise });
    }
    return promise;
  },

  updateReminderSettings: async (payload, source) => {
    const data = source
      ? await source.updateReminderSettings(payload)
      : await apiUpdateReminderSettings(payload);
    set({ reminderSettings: data, reminderSettingsLoaded: true });
    return data;
  },

  updateTenantSettings: async (payload, source) => {
    const data = source
      ? await source.updateTenantSettings(payload)
      : await apiUpdateTenantSettings(payload);
    set({ tenantSettings: data, tenantSettingsLoaded: true });
    return data;
  },

  savePublicApiKeyOrigins: async (origins, source) => {
    const data = source
      ? await source.savePublicApiKeyOrigins(origins)
      : await apiSavePublicApiKeyOrigins(origins);
    set({
      publicApiKey: data,
      publicApiKeyLoaded: true,
      publicApiKeyInFlight: null,
    });
    return data;
  },

  regeneratePublicApiKey: async (source) => {
    const data = source
      ? await source.regeneratePublicApiKey()
      : await apiRegeneratePublicApiKey();
    set({
      publicApiKey: data,
      publicApiKeyLoaded: true,
      publicApiKeyInFlight: null,
    });
    return data;
  },

  revokePublicApiKey: async (source) => {
    if (source) {
      await source.revokePublicApiKey();
    } else {
      await apiRevokePublicApiKey();
    }
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
  source?: SettingsDataSourceContract,
): Promise<ReminderSettings | null> {
  const epoch = get()._settingsEpoch;
  try {
    const data = source
      ? await source.loadReminderSettings()
      : await getReminderSettings();
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
  source?: SettingsDataSourceContract,
): Promise<TenantSettings | null> {
  const epoch = get()._settingsEpoch;
  try {
    const data = source
      ? await source.loadTenantSettings()
      : await getTenantSettings();
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
  source?: SettingsDataSourceContract,
): Promise<TimezoneOption[]> {
  const epoch = get()._settingsEpoch;
  try {
    const data = source
      ? await source.loadTimezoneOptions()
      : await getTimezones();
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
  source?: SettingsDataSourceContract,
): Promise<Mailbox | null> {
  const epoch = get()._settingsEpoch;
  try {
    const data = source
      ? await source.loadMailbox()
      : await apiGetMailbox();
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
  source?: SettingsDataSourceContract,
): Promise<PublicApiKeyConfig | null> {
  const epoch = get()._settingsEpoch;
  try {
    const data = source
      ? await source.loadPublicApiKey()
      : await apiGetPublicApiKey();
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
