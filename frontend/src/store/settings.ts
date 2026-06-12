import { create } from "zustand";
import {
  getReminderSettings,
  updateReminderSettings as apiUpdateReminderSettings,
  getTimezones,
  type ReminderSettings,
  type ReminderSettingsUpdate,
  type TimezoneOption,
} from "@/features/admin/services/reminder-api";

interface SettingsState {
  // Cache state
  reminderSettings: ReminderSettings | null;
  timezoneOptions: TimezoneOption[];
  settingsLoaded: boolean;
  timezonesLoaded: boolean;
  settingsInFlight: Promise<ReminderSettings | null> | null;
  timezonesInFlight: Promise<TimezoneOption[]> | null;
  settingsLoadError: string | null;

  // Actions
  loadTenantSettings: () => Promise<{
    reminderSettings: ReminderSettings | null;
    timezoneOptions: TimezoneOption[];
  }>;
  updateReminderSettings: (
    settings: ReminderSettingsUpdate
  ) => Promise<ReminderSettings>;
  clearSettingsCache: () => void;
}

export const useSettingsStore = create<SettingsState>((set, get) => ({
  // Initial state
  reminderSettings: null,
  timezoneOptions: [],
  settingsLoaded: false,
  timezonesLoaded: false,
  settingsInFlight: null,
  timezonesInFlight: null,
  settingsLoadError: null,

  // Load settings with caching and deduplication
  loadTenantSettings: async () => {
    const state = get();

    // Already fully loaded — return cached data
    if (state.settingsLoaded && state.timezonesLoaded) {
      return {
        reminderSettings: state.reminderSettings,
        timezoneOptions: state.timezoneOptions,
      };
    }

    // Deduplicate: reuse in-flight promises
    const settingsPromise = state.settingsInFlight || loadSettings(set);
    const timezonesPromise = state.timezonesInFlight || loadTimezones(set);

    // Set in-flight promises if not already set
    if (!state.settingsInFlight) {
      set({ settingsInFlight: settingsPromise });
    }
    if (!state.timezonesInFlight) {
      set({ timezonesInFlight: timezonesPromise });
    }

    try {
      const [settings, timezones] = await Promise.all([
        settingsPromise,
        timezonesPromise,
      ]);

      return {
        reminderSettings: settings,
        timezoneOptions: timezones,
      };
    } catch (error) {
      console.error("[settings] Failed to load tenant settings:", error);
      throw error;
    }
  },

  // Update settings and cache
  updateReminderSettings: async (payload) => {
    const data = await apiUpdateReminderSettings(payload);

    // Update cache from successful response
    set({
      reminderSettings: data,
      settingsLoaded: true,
    });

    return data;
  },

  // Clear cache (on logout, tenant switch)
  clearSettingsCache: () => {
    set({
      reminderSettings: null,
      timezoneOptions: [],
      settingsLoaded: false,
      timezonesLoaded: false,
      settingsInFlight: null,
      timezonesInFlight: null,
      settingsLoadError: null,
    });
  },
}));

// Internal helpers
async function loadSettings(
  set: (partial: Partial<SettingsState>) => void
): Promise<ReminderSettings | null> {
  try {
    const data = await getReminderSettings();
    set({
      reminderSettings: data,
      settingsLoaded: true,
      settingsLoadError: null,
      settingsInFlight: null,
    });
    return data;
  } catch (error: any) {
    const detail = error?.response?.data?.detail;
    const msg =
      typeof detail === "string"
        ? detail
        : Array.isArray(detail)
          ? detail.map((d: any) => d.msg || "Unknown error").join("; ")
          : "Failed to load settings";

    set({
      settingsLoadError: msg,
      settingsInFlight: null,
    });
    throw error;
  }
}

async function loadTimezones(
  set: (partial: Partial<SettingsState>) => void
): Promise<TimezoneOption[]> {
  try {
    const data = await getTimezones();
    set({
      timezoneOptions: data,
      timezonesLoaded: true,
      timezonesInFlight: null,
    });
    return data;
  } catch (error) {
    // Timezone failure is non-fatal
    console.warn("[settings] Failed to load timezone options:", error);
    set({
      timezoneOptions: [],
      timezonesLoaded: false,
      timezonesInFlight: null,
    });
    return [];
  }
}
