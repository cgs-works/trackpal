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
  type TenantSettings,
  type TenantSettingsUpdate,
  type TimezoneOption,
} from "@/features/admin/services/settings-api";

interface SettingsState {
  reminderSettings: ReminderSettings | null;
  tenantSettings: TenantSettings | null;
  timezoneOptions: TimezoneOption[];
  reminderSettingsLoaded: boolean;
  tenantSettingsLoaded: boolean;
  timezonesLoaded: boolean;
  reminderSettingsInFlight: Promise<ReminderSettings | null> | null;
  tenantSettingsInFlight: Promise<TenantSettings | null> | null;
  timezonesInFlight: Promise<TimezoneOption[]> | null;
  settingsLoadError: string | null;
  _settingsEpoch: number;

  loadReminderSettings: () => Promise<ReminderSettings | null>;
  loadTenantSettings: () => Promise<TenantSettings | null>;
  loadTimezoneOptions: () => Promise<TimezoneOption[]>;
  updateReminderSettings: (
    settings: ReminderSettingsUpdate
  ) => Promise<ReminderSettings>;
  updateTenantSettings: (
    settings: TenantSettingsUpdate
  ) => Promise<TenantSettings>;
  clearSettingsCache: () => void;
}

export const useSettingsStore = create<SettingsState>((set, get) => ({
  reminderSettings: null,
  tenantSettings: null,
  timezoneOptions: [],
  reminderSettingsLoaded: false,
  tenantSettingsLoaded: false,
  timezonesLoaded: false,
  reminderSettingsInFlight: null,
  tenantSettingsInFlight: null,
  timezonesInFlight: null,
  settingsLoadError: null,
  _settingsEpoch: 0,

  loadReminderSettings: async () => {
    const state = get();
    if (state.reminderSettingsLoaded) return state.reminderSettings;
    const promise = state.reminderSettingsInFlight || loadReminderSettings(set, get);
    if (!state.reminderSettingsInFlight) {
      set({ reminderSettingsInFlight: promise });
    }
    return promise;
  },

  loadTenantSettings: async () => {
    const state = get();
    if (state.tenantSettingsLoaded) return state.tenantSettings;
    const promise = state.tenantSettingsInFlight || loadTenantSettings(set, get);
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

  clearSettingsCache: () => {
    set({
      reminderSettings: null,
      tenantSettings: null,
      timezoneOptions: [],
      reminderSettingsLoaded: false,
      tenantSettingsLoaded: false,
      timezonesLoaded: false,
      reminderSettingsInFlight: null,
      tenantSettingsInFlight: null,
      timezonesInFlight: null,
      settingsLoadError: null,
      _settingsEpoch: get()._settingsEpoch + 1,
    });
  },
}));

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
    const err = error as { response?: { data?: { detail?: string | Array<{ msg?: string }> } } };
    const detail = err?.response?.data?.detail;
    const msg =
      typeof detail === "string"
        ? detail
        : Array.isArray(detail)
          ? detail.map((d) => d.msg || "Unknown error").join("; ")
          : "Failed to load reminder settings";
    set({ settingsLoadError: msg, reminderSettingsInFlight: null });
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
    const err = error as { response?: { data?: { detail?: string | Array<{ msg?: string }> } } };
    const detail = err?.response?.data?.detail;
    const msg =
      typeof detail === "string"
        ? detail
        : Array.isArray(detail)
          ? detail.map((d) => d.msg || "Unknown error").join("; ")
          : "Failed to load tenant settings";
    set({ settingsLoadError: msg, tenantSettingsInFlight: null });
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
