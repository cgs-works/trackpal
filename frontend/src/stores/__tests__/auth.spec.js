import { describe, it, expect, beforeEach, vi } from "vitest";
import { setActivePinia, createPinia } from "pinia";
import { useAuthStore } from "../auth";

// Mock axios before importing the store
vi.mock("axios", () => {
	const mockAxios = {
		post: vi.fn(),
		get: vi.fn(),
		put: vi.fn(),
		create: vi.fn(() => mockAxios),
		interceptors: {
			request: { use: vi.fn() },
			response: { use: vi.fn() },
		},
	};
	return { default: mockAxios };
});

/** Factory for a normalised subscription-settings response */
function makeSettingsResponse(overrides = {}) {
	return {
		data: {
			reminders_enabled: true,
			timezone: "America/New_York",
			warning_days: [7, 3],
			reminder_time: "10:00",
			recipient_mode: "both",
			...overrides,
		},
	};
}

/** Factory for a timezone options response */
function makeTzResponse() {
	return {
		data: [
			{ value: "UTC", label: "UTC" },
			{ value: "America/New_York", label: "Eastern (UTC-5)" },
		],
	};
}

describe("auth store — reminder settings cache", () => {
	beforeEach(() => {
		setActivePinia(createPinia());
		localStorage.clear();
		vi.clearAllMocks();
	});

	describe("initial cache state", () => {
		it("starts with null/empty cache values", () => {
			const store = useAuthStore();

			expect(store.reminderSettings).toBeNull();
			expect(store.timezoneOptions).toEqual([]);
			expect(store.settingsLoaded).toBe(false);
			expect(store.timezonesLoaded).toBe(false);
			expect(store.settingsInFlight).toBeNull();
			expect(store.tenantContextKey).toBeNull();
			expect(store.settingsLoadError).toBeNull();
		});
	});

	describe("_clearTenantSettingsCache", () => {
		it("resets every cache field to its initial value", () => {
			const store = useAuthStore();

			// Set non-default values
			store.reminderSettings = { reminders_enabled: true };
			store.timezoneOptions = [{ value: "UTC", label: "UTC" }];
			store.settingsLoaded = true;
			store.timezonesLoaded = true;
			store.settingsInFlight = Promise.resolve();
			store.tenantContextKey = "user-42";
			store.settingsLoadError = "some error";

			store._clearTenantSettingsCache();

			expect(store.reminderSettings).toBeNull();
			expect(store.timezoneOptions).toEqual([]);
			expect(store.settingsLoaded).toBe(false);
			expect(store.timezonesLoaded).toBe(false);
			expect(store.settingsInFlight).toBeNull();
			expect(store.tenantContextKey).toBeNull();
			expect(store.settingsLoadError).toBeNull();
		});
	});

	describe("_deriveTenantContextKey", () => {
		it("returns activeTenantId when set (Master in support mode)", () => {
			const store = useAuthStore();
			store.activeTenantId = "tenant-99";

			const key = store._deriveTenantContextKey();

			expect(key).toBe("tenant-99");
		});

		it("returns user id when activeTenantId is not set (direct tenant session)", () => {
			const store = useAuthStore();
			store.user = { id: "user-1", username: "test-tenant" };

			const key = store._deriveTenantContextKey();

			expect(key).toBe("user-1");
		});

		it("returns null when neither tenant id nor user id is available", () => {
			const store = useAuthStore();
			store.activeTenantId = null;
			store.user = null;

			const key = store._deriveTenantContextKey();

			expect(key).toBeNull();
		});
	});

	describe("cache reset on auth actions", () => {
		it("clears cache before login", async () => {
			const store = useAuthStore();
			// Pre-populate cache
			store.reminderSettings = { reminders_enabled: true };
			store.settingsLoaded = true;
			store.tenantContextKey = "stale-key";

			const axios = await import("axios");
			axios.default.post.mockResolvedValueOnce({
				data: {
					access_token: "new-token",
					refresh_token: "new-refresh",
					user: { id: "user-2", role: "tenant" },
					active_tenant_id: null,
				},
			});

			await store.login("test", "pass");

			// Cache should have been cleared before the POST
			expect(store.reminderSettings).toBeNull();
			expect(store.settingsLoaded).toBe(false);
			expect(store.tenantContextKey).toBeNull();
		});

		it("clears cache before logout", async () => {
			const store = useAuthStore();
			store.token = "some-token";
			store.reminderSettings = { reminders_enabled: true };
			store.settingsLoaded = true;
			store.tenantContextKey = "user-42";

			const axios = await import("axios");
			axios.default.post.mockResolvedValueOnce({ data: {} });

			await store.logout();

			expect(store.reminderSettings).toBeNull();
			expect(store.settingsLoaded).toBe(false);
			expect(store.tenantContextKey).toBeNull();
		});

		it("clears cache before switchTenant", async () => {
			const store = useAuthStore();
			store.token = "some-token";
			store.reminderSettings = { reminders_enabled: true };
			store.settingsLoaded = true;
			store.tenantContextKey = "tenant-A";

			const axios = await import("axios");
			axios.default.post.mockResolvedValueOnce({
				data: {
					access_token: "switched-token",
					refresh_token: "switched-refresh",
					user: { id: "master-1", role: "master" },
					active_tenant_id: "tenant-B",
				},
			});

			await store.switchTenant("tenant-B");

			expect(store.reminderSettings).toBeNull();
			expect(store.settingsLoaded).toBe(false);
			expect(store.tenantContextKey).toBeNull();
		});

		it("clears cache before exitTenantContext", async () => {
			const store = useAuthStore();
			store.token = "some-token";
			store.reminderSettings = { reminders_enabled: true };
			store.settingsLoaded = true;
			store.tenantContextKey = "tenant-A";

			const axios = await import("axios");
			axios.default.post.mockResolvedValueOnce({
				data: {
					access_token: "exit-token",
					refresh_token: "exit-refresh",
					user: { id: "master-1", role: "master" },
					active_tenant_id: null,
				},
			});

			await store.exitTenantContext();

			expect(store.reminderSettings).toBeNull();
			expect(store.settingsLoaded).toBe(false);
			expect(store.tenantContextKey).toBeNull();
		});
	});

	describe("loadTenantSettings", () => {
		it("fetches settings and timezones on first load and populates cache", async () => {
			const store = useAuthStore();
			store.user = { id: "user-1", role: "tenant" };

			const axios = await import("axios");
			axios.default.get.mockResolvedValueOnce(makeSettingsResponse());
			axios.default.get.mockResolvedValueOnce(makeTzResponse());

			const result = await store.loadTenantSettings();

			expect(axios.default.get).toHaveBeenCalledTimes(2);
			expect(axios.default.get).toHaveBeenCalledWith(
				"/subscription-settings",
			);
			expect(axios.default.get).toHaveBeenCalledWith(
				"/subscription-settings/timezones",
			);

			expect(store.reminderSettings).toEqual(
				expect.objectContaining({
					reminders_enabled: true,
					timezone: "America/New_York",
				}),
			);
			expect(store.timezoneOptions).toHaveLength(2);
			expect(store.settingsLoaded).toBe(true);
			expect(store.timezonesLoaded).toBe(true);
			expect(store.settingsLoadError).toBeNull();
			expect(store.settingsInFlight).toBeNull();

			expect(result).toEqual({
				reminderSettings: store.reminderSettings,
				timezoneOptions: store.timezoneOptions,
			});
		});

		it("returns cached data when already fully loaded", async () => {
			const store = useAuthStore();
			// Prime the cache
			store.reminderSettings = { reminders_enabled: false };
			store.timezoneOptions = [{ value: "UTC", label: "UTC" }];
			store.settingsLoaded = true;
			store.timezonesLoaded = true;

			const axios = await import("axios");
			const result = await store.loadTenantSettings();

			// Should resolve immediately without network calls
			expect(axios.default.get).not.toHaveBeenCalled();
			expect(result).toEqual({
				reminderSettings: { reminders_enabled: false },
				timezoneOptions: [{ value: "UTC", label: "UTC" }],
			});
		});

		it("deduplicates concurrent calls by reusing the in-flight promise", async () => {
			const store = useAuthStore();
			store.user = { id: "user-1", role: "tenant" };

			const axios = await import("axios");
			// Return a promise that we can control
			let resolveSettings, resolveTz;
			const settingsPromise = new Promise((r) => {
				resolveSettings = r;
			});
			const tzPromise = new Promise((r) => {
				resolveTz = r;
			});

			axios.default.get.mockReturnValueOnce(settingsPromise);
			axios.default.get.mockReturnValueOnce(tzPromise);

			// Two concurrent calls
			const call1 = store.loadTenantSettings();
			const call2 = store.loadTenantSettings();

			// Both should share the same in-flight promise
			expect(store.settingsInFlight).toBeTruthy();

			// Resolve both requests
			resolveSettings(makeSettingsResponse());
			resolveTz(makeTzResponse());

			const [result1, result2] = await Promise.all([call1, call2]);

			// Only one GET per endpoint — dedup worked
			expect(axios.default.get).toHaveBeenCalledTimes(2);
			expect(result1).toEqual(result2);
			expect(store.settingsInFlight).toBeNull();
		});

		it("does not mark cache as loaded when settings request fails", async () => {
			const store = useAuthStore();
			store.user = { id: "user-1", role: "tenant" };

			const axios = await import("axios");
			const error = new Error("Network error");
			error.response = {
				data: { detail: "Server error" },
			};
			// First attempt: both GETs fire via Promise.all
			axios.default.get.mockRejectedValueOnce(error);
			axios.default.get.mockResolvedValueOnce(makeTzResponse());
			// Second attempt: need fresh mocks for both endpoints
			axios.default.get.mockResolvedValueOnce(makeSettingsResponse());
			axios.default.get.mockResolvedValueOnce(makeTzResponse());

			// First attempt — fails (Promise.all rejects fast)
			await expect(store.loadTenantSettings()).rejects.toThrow();

			expect(store.settingsLoaded).toBe(false);
			expect(store.timezonesLoaded).toBe(false);
			expect(store.reminderSettings).toBeNull();
			expect(store.settingsLoadError).toBe("Server error");
			expect(store.settingsInFlight).toBeNull();

			// Second attempt — should retry and succeed
			const result = await store.loadTenantSettings();
			expect(result).toBeTruthy();
			expect(store.settingsLoaded).toBe(true);
			expect(store.settingsLoadError).toBeNull();

			// First attempt: 2 GETs + second attempt: 2 GETs = 4 total
			expect(axios.default.get).toHaveBeenCalledTimes(4);
		});

		it("populates settings cache when timezone request fails (non-fatal)", async () => {
			const store = useAuthStore();
			store.user = { id: "user-1", role: "tenant" };

			const axios = await import("axios");
			// Settings succeeds
			axios.default.get.mockResolvedValueOnce(makeSettingsResponse());
			// Timezones fail
			const tzError = new Error("timezone error");
			tzError.response = {
				data: { message: "timezone service unavailable" },
			};
			axios.default.get.mockRejectedValueOnce(tzError);

			const result = await store.loadTenantSettings();

			// Settings should be cached, timezones should be empty
			expect(store.reminderSettings).toEqual(
				expect.objectContaining({
					reminders_enabled: true,
					timezone: "America/New_York",
				}),
			);
			expect(store.settingsLoaded).toBe(true);
			expect(store.timezonesLoaded).toBe(false);
			expect(store.timezoneOptions).toEqual([]);
			expect(store.settingsLoadError).toBeNull();

			expect(result).toBeTruthy();
			expect(result.reminderSettings).toBeTruthy();
			expect(result.timezoneOptions).toEqual([]);
		});

		it("discards late response when tenant context changes during load", async () => {
			const store = useAuthStore();
			store.user = { id: "user-1", role: "tenant" };

			const axios = await import("axios");
			let resolveSettings, resolveTz;
			const settingsPromise = new Promise((r) => {
				resolveSettings = r;
			});
			const tzPromise = new Promise((r) => {
				resolveTz = r;
			});

			axios.default.get.mockReturnValueOnce(settingsPromise);
			axios.default.get.mockReturnValueOnce(tzPromise);

			// Start loading with tenant context A
			store.activeTenantId = "tenant-A";
			const loadPromise = store.loadTenantSettings();

			// Context switches to tenant B while request is in flight
			store._clearTenantSettingsCache();
			store.activeTenantId = "tenant-B";
			store.user = { id: "master-1", role: "master" };

			// Resolve the in-flight requests
			resolveSettings(makeSettingsResponse());
			resolveTz(makeTzResponse());

			const result = await loadPromise;

			// Result should be null (discarded)
			expect(result).toBeNull();
			// Cache should still be cleared
			expect(store.reminderSettings).toBeNull();
			expect(store.settingsLoaded).toBe(false);
			expect(store.settingsInFlight).toBeNull();
		});
	});

	describe("updateReminderSettings", () => {
		it("PUTs new settings and updates cache from server response", async () => {
			const store = useAuthStore();
			const input = {
				reminders_enabled: true,
				timezone: "Europe/Madrid",
				warning_days: [7, 1],
				reminder_time: "08:00",
				recipient_mode: "tenant_only",
			};

			const axios = await import("axios");
			// Server response may normalize the data
			axios.default.put.mockResolvedValueOnce(
				makeSettingsResponse({
					timezone: "Europe/Madrid",
					warning_days: [7, 1],
				}),
			);

			const result = await store.updateReminderSettings(input);

			expect(axios.default.put).toHaveBeenCalledWith(
				"/subscription-settings",
				input,
			);
			expect(store.reminderSettings).toEqual(
				expect.objectContaining({
					reminders_enabled: true,
					timezone: "Europe/Madrid",
					warning_days: [7, 1],
				}),
			);
			expect(result).toEqual(store.reminderSettings);
		});

		it("does not modify cache when PUT fails", async () => {
			const store = useAuthStore();
			store.reminderSettings = {
				reminders_enabled: false,
				timezone: "UTC",
				warning_days: [7, 3, 1],
				reminder_time: "09:00",
				recipient_mode: "tenant_only",
			};

			const axios = await import("axios");
			const error = new Error("Validation error");
			error.response = { status: 422, data: { detail: "Invalid timezone" } };
			axios.default.put.mockRejectedValueOnce(error);

			await expect(
				store.updateReminderSettings({ timezone: "Invalid/Zone" }),
			).rejects.toThrow();

			// Cache should remain unchanged
			expect(store.reminderSettings).toEqual({
				reminders_enabled: false,
				timezone: "UTC",
				warning_days: [7, 3, 1],
				reminder_time: "09:00",
				recipient_mode: "tenant_only",
			});
		});
	});
});

import { describe, it, expect, beforeEach, vi } from "vitest";
import { setActivePinia, createPinia } from "pinia";
import { useAuthStore } from "../auth";

// Mock axios before importing the store
vi.mock("axios", () => {
	const mockAxios = {
		post: vi.fn(),
		get: vi.fn(),
		put: vi.fn(),
		create: vi.fn(() => mockAxios),
		interceptors: {
			request: { use: vi.fn() },
			response: { use: vi.fn() },
		},
	};
	return { default: mockAxios };
});

/** Factory for a normalised subscription-settings response */
function makeSettingsResponse(overrides = {}) {
	return {
		data: {
			reminders_enabled: true,
			timezone: "America/New_York",
			warning_days: [7, 3],
			reminder_time: "10:00",
			recipient_mode: "both",
			...overrides,
		},
	};
}

/** Factory for a timezone options response */
function makeTzResponse() {
	return {
		data: [
			{ value: "UTC", label: "UTC" },
			{ value: "America/New_York", label: "Eastern (UTC-5)" },
		],
	};
}

describe("auth store — reminder settings cache", () => {
	beforeEach(() => {
		setActivePinia(createPinia());
		localStorage.clear();
		vi.clearAllMocks();
	});

	describe("initial cache state", () => {
		it("starts with null/empty cache values", () => {
			const store = useAuthStore();

			expect(store.reminderSettings).toBeNull();
			expect(store.timezoneOptions).toEqual([]);
			expect(store.settingsLoaded).toBe(false);
			expect(store.timezonesLoaded).toBe(false);
			expect(store.settingsInFlight).toBeNull();
			expect(store.tenantContextKey).toBeNull();
			expect(store.settingsLoadError).toBeNull();
		});
	});

	describe("_clearTenantSettingsCache", () => {
		it("resets every cache field to its initial value", () => {
			const store = useAuthStore();

			// Set non-default values
			store.reminderSettings = { reminders_enabled: true };
			store.timezoneOptions = [{ value: "UTC", label: "UTC" }];
			store.settingsLoaded = true;
			store.timezonesLoaded = true;
			store.settingsInFlight = Promise.resolve();
			store.tenantContextKey = "user-42";
			store.settingsLoadError = "some error";

			store._clearTenantSettingsCache();

			expect(store.reminderSettings).toBeNull();
			expect(store.timezoneOptions).toEqual([]);
			expect(store.settingsLoaded).toBe(false);
			expect(store.timezonesLoaded).toBe(false);
			expect(store.settingsInFlight).toBeNull();
			expect(store.tenantContextKey).toBeNull();
			expect(store.settingsLoadError).toBeNull();
		});
	});

	describe("_deriveTenantContextKey", () => {
		it("returns activeTenantId when set (Master in support mode)", () => {
			const store = useAuthStore();
			store.activeTenantId = "tenant-99";

			const key = store._deriveTenantContextKey();

			expect(key).toBe("tenant-99");
		});

		it("returns user id when activeTenantId is not set (direct tenant session)", () => {
			const store = useAuthStore();
			store.user = { id: "user-1", username: "test-tenant" };

			const key = store._deriveTenantContextKey();

			expect(key).toBe("user-1");
		});

		it("returns null when neither tenant id nor user id is available", () => {
			const store = useAuthStore();
			store.activeTenantId = null;
			store.user = null;

			const key = store._deriveTenantContextKey();

			expect(key).toBeNull();
		});
	});

	describe("cache reset on auth actions", () => {
		it("clears cache before login", async () => {
			const store = useAuthStore();
			// Pre-populate cache
			store.reminderSettings = { reminders_enabled: true };
			store.settingsLoaded = true;
			store.tenantContextKey = "stale-key";

			const axios = await import("axios");
			axios.default.post.mockResolvedValueOnce({
				data: {
					access_token: "new-token",
					refresh_token: "new-refresh",
					user: { id: "user-2", role: "tenant" },
					active_tenant_id: null,
				},
			});

			await store.login("test", "pass");

			// Cache should have been cleared before the POST
			expect(store.reminderSettings).toBeNull();
			expect(store.settingsLoaded).toBe(false);
			expect(store.tenantContextKey).toBeNull();
		});

		it("clears cache before logout", async () => {
			const store = useAuthStore();
			store.token = "some-token";
			store.reminderSettings = { reminders_enabled: true };
			store.settingsLoaded = true;
			store.tenantContextKey = "user-42";

			const axios = await import("axios");
			axios.default.post.mockResolvedValueOnce({ data: {} });

			await store.logout();

			expect(store.reminderSettings).toBeNull();
			expect(store.settingsLoaded).toBe(false);
			expect(store.tenantContextKey).toBeNull();
		});

		it("clears cache before switchTenant", async () => {
			const store = useAuthStore();
			store.token = "some-token";
			store.reminderSettings = { reminders_enabled: true };
			store.settingsLoaded = true;
			store.tenantContextKey = "tenant-A";

			const axios = await import("axios");
			axios.default.post.mockResolvedValueOnce({
				data: {
					access_token: "switched-token",
					refresh_token: "switched-refresh",
					user: { id: "master-1", role: "master" },
					active_tenant_id: "tenant-B",
				},
			});

			await store.switchTenant("tenant-B");

			expect(store.reminderSettings).toBeNull();
			expect(store.settingsLoaded).toBe(false);
			expect(store.tenantContextKey).toBeNull();
		});

		it("clears cache before exitTenantContext", async () => {
			const store = useAuthStore();
			store.token = "some-token";
			store.reminderSettings = { reminders_enabled: true };
			store.settingsLoaded = true;
			store.tenantContextKey = "tenant-A";

			const axios = await import("axios");
			axios.default.post.mockResolvedValueOnce({
				data: {
					access_token: "exit-token",
					refresh_token: "exit-refresh",
					user: { id: "master-1", role: "master" },
					active_tenant_id: null,
				},
			});

			await store.exitTenantContext();

			expect(store.reminderSettings).toBeNull();
			expect(store.settingsLoaded).toBe(false);
			expect(store.tenantContextKey).toBeNull();
		});
	});

	describe("loadTenantSettings", () => {
		it("fetches settings and timezones on first load and populates cache", async () => {
			const store = useAuthStore();
			store.user = { id: "user-1", role: "tenant" };

			const axios = await import("axios");
			axios.default.get.mockResolvedValueOnce(makeSettingsResponse());
			axios.default.get.mockResolvedValueOnce(makeTzResponse());

			const result = await store.loadTenantSettings();

			expect(axios.default.get).toHaveBeenCalledTimes(2);
			expect(axios.default.get).toHaveBeenCalledWith("/subscription-settings");
			expect(axios.default.get).toHaveBeenCalledWith(
				"/subscription-settings/timezones",
			);

			expect(store.reminderSettings).toEqual(
				expect.objectContaining({
					reminders_enabled: true,
					timezone: "America/New_York",
				}),
			);
			expect(store.timezoneOptions).toHaveLength(2);
			expect(store.settingsLoaded).toBe(true);
			expect(store.timezonesLoaded).toBe(true);
			expect(store.settingsLoadError).toBeNull();
			expect(store.settingsInFlight).toBeNull();

			expect(result).toEqual({
				reminderSettings: store.reminderSettings,
				timezoneOptions: store.timezoneOptions,
			});
		});

		it("returns cached data when already fully loaded", async () => {
			const store = useAuthStore();
			// Prime the cache
			store.reminderSettings = { reminders_enabled: false };
			store.timezoneOptions = [{ value: "UTC", label: "UTC" }];
			store.settingsLoaded = true;
			store.timezonesLoaded = true;

			const axios = await import("axios");
			const result = await store.loadTenantSettings();

			// Should resolve immediately without network calls
			expect(axios.default.get).not.toHaveBeenCalled();
			expect(result).toEqual({
				reminderSettings: { reminders_enabled: false },
				timezoneOptions: [{ value: "UTC", label: "UTC" }],
			});
		});

		it("deduplicates concurrent calls by reusing the in-flight promise", async () => {
			const store = useAuthStore();
			store.user = { id: "user-1", role: "tenant" };

			const axios = await import("axios");
			// Return a promise that we can control
			let resolveSettings, resolveTz;
			const settingsPromise = new Promise((r) => {
				resolveSettings = r;
			});
			const tzPromise = new Promise((r) => {
				resolveTz = r;
			});

			axios.default.get.mockReturnValueOnce(settingsPromise);
			axios.default.get.mockReturnValueOnce(tzPromise);

			// Two concurrent calls
			const call1 = store.loadTenantSettings();
			const call2 = store.loadTenantSettings();

			// Both should share the same in-flight promise
			expect(store.settingsInFlight).toBeTruthy();

			// Resolve both requests
			resolveSettings(makeSettingsResponse());
			resolveTz(makeTzResponse());

			const [result1, result2] = await Promise.all([call1, call2]);

			// Only one GET per endpoint — dedup worked
			expect(axios.default.get).toHaveBeenCalledTimes(2);
			expect(result1).toEqual(result2);
			expect(store.settingsInFlight).toBeNull();
		});

		it("does not mark cache as loaded when settings request fails", async () => {
			const store = useAuthStore();
			store.user = { id: "user-1", role: "tenant" };

			const axios = await import("axios");
			const error = new Error("Network error");
			error.response = {
				data: { detail: "Server error" },
			};
			// First attempt: both GETs fire via Promise.all
			axios.default.get.mockRejectedValueOnce(error);
			axios.default.get.mockResolvedValueOnce(makeTzResponse());
			// Second attempt: need fresh mocks for both endpoints
			axios.default.get.mockResolvedValueOnce(makeSettingsResponse());
			axios.default.get.mockResolvedValueOnce(makeTzResponse());

			// First attempt — fails (Promise.all rejects fast)
			await expect(store.loadTenantSettings()).rejects.toThrow();

			expect(store.settingsLoaded).toBe(false);
			expect(store.timezonesLoaded).toBe(false);
			expect(store.reminderSettings).toBeNull();
			expect(store.settingsLoadError).toBe("Server error");
			expect(store.settingsInFlight).toBeNull();

			// Second attempt — should retry and succeed
			const result = await store.loadTenantSettings();
			expect(result).toBeTruthy();
			expect(store.settingsLoaded).toBe(true);
			expect(store.settingsLoadError).toBeNull();

			// First attempt: 2 GETs + second attempt: 2 GETs = 4 total
			expect(axios.default.get).toHaveBeenCalledTimes(4);
		});

		it("populates settings cache when timezone request fails (non-fatal)", async () => {
			const store = useAuthStore();
			store.user = { id: "user-1", role: "tenant" };

			const axios = await import("axios");
			// Settings succeeds
			axios.default.get.mockResolvedValueOnce(makeSettingsResponse());
			// Timezones fail
			const tzError = new Error("timezone error");
			tzError.response = {
				data: { message: "timezone service unavailable" },
			};
			axios.default.get.mockRejectedValueOnce(tzError);

			const result = await store.loadTenantSettings();

			// Settings should be cached, timezones should be empty
			expect(store.reminderSettings).toEqual(
				expect.objectContaining({
					reminders_enabled: true,
					timezone: "America/New_York",
				}),
			);
			expect(store.settingsLoaded).toBe(true);
			expect(store.timezonesLoaded).toBe(false);
			expect(store.timezoneOptions).toEqual([]);
			expect(store.settingsLoadError).toBeNull();

			expect(result).toBeTruthy();
			expect(result.reminderSettings).toBeTruthy();
			expect(result.timezoneOptions).toEqual([]);
		});

		it("discards late response when tenant context changes during load", async () => {
			const store = useAuthStore();
			store.user = { id: "user-1", role: "tenant" };

			const axios = await import("axios");
			let resolveSettings, resolveTz;
			const settingsPromise = new Promise((r) => {
				resolveSettings = r;
			});
			const tzPromise = new Promise((r) => {
				resolveTz = r;
			});

			axios.default.get.mockReturnValueOnce(settingsPromise);
			axios.default.get.mockReturnValueOnce(tzPromise);

			// Start loading with tenant context A
			store.activeTenantId = "tenant-A";
			const loadPromise = store.loadTenantSettings();

			// Context switches to tenant B while request is in flight
			store._clearTenantSettingsCache();
			store.activeTenantId = "tenant-B";
			store.user = { id: "master-1", role: "master" };

			// Resolve the in-flight requests
			resolveSettings(makeSettingsResponse());
			resolveTz(makeTzResponse());

			const result = await loadPromise;

			// Result should be null (discarded)
			expect(result).toBeNull();
			// Cache should still be cleared
			expect(store.reminderSettings).toBeNull();
			expect(store.settingsLoaded).toBe(false);
			expect(store.settingsInFlight).toBeNull();
		});
	});

	describe("updateReminderSettings", () => {
		it("PUTs new settings and updates cache from server response", async () => {
			const store = useAuthStore();
			const input = {
				reminders_enabled: true,
				timezone: "Europe/Madrid",
				warning_days: [7, 1],
				reminder_time: "08:00",
				recipient_mode: "tenant_only",
			};

			const axios = await import("axios");
			// Server response may normalize the data
			axios.default.put.mockResolvedValueOnce(
				makeSettingsResponse({
					timezone: "Europe/Madrid",
					warning_days: [7, 1],
				}),
			);

			const result = await store.updateReminderSettings(input);

			expect(axios.default.put).toHaveBeenCalledWith(
				"/subscription-settings",
				input,
			);
			expect(store.reminderSettings).toEqual(
				expect.objectContaining({
					reminders_enabled: true,
					timezone: "Europe/Madrid",
					warning_days: [7, 1],
				}),
			);
			expect(result).toEqual(store.reminderSettings);
		});

		it("does not modify cache when PUT fails", async () => {
			const store = useAuthStore();
			store.reminderSettings = {
				reminders_enabled: false,
				timezone: "UTC",
				warning_days: [7, 3, 1],
				reminder_time: "09:00",
				recipient_mode: "tenant_only",
			};

			const axios = await import("axios");
			const error = new Error("Validation error");
			error.response = { status: 422, data: { detail: "Invalid timezone" } };
			axios.default.put.mockRejectedValueOnce(error);

			await expect(
				store.updateReminderSettings({ timezone: "Invalid/Zone" }),
			).rejects.toThrow();

			// Cache should remain unchanged
			expect(store.reminderSettings).toEqual({
				reminders_enabled: false,
				timezone: "UTC",
				warning_days: [7, 3, 1],
				reminder_time: "09:00",
				recipient_mode: "tenant_only",
			});
		});
	});
});
