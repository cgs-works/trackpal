import { describe, expect, it } from "vitest";
import { resolveSafeHelpNavigation } from "./safe-navigation";

describe("resolveSafeHelpNavigation", () => {
  it("allows a Dashboard destination", () => {
    expect(
      resolveSafeHelpNavigation({
        route: "/admin/dashboard",
        settings_category: null,
      }),
    ).toEqual({ to: "/admin/dashboard" });
  });

  it("allows only known Settings categories", () => {
    expect(
      resolveSafeHelpNavigation({
        route: "/admin/settings",
        settings_category: "reminders",
      }),
    ).toEqual({ to: "/admin/settings", search: { category: "reminders" } });

    expect(
      resolveSafeHelpNavigation({
        route: "/admin/settings",
        settings_category: "submit-form",
      }),
    ).toBeNull();
  });

  it("allows the authenticated Help Center destination", () => {
    expect(
      resolveSafeHelpNavigation({
        route: "/admin/help",
        settings_category: null,
      }),
    ).toEqual({ to: "/admin/help" });
  });

  it("allows Pro module destinations without exposing mutation routes", () => {
    expect(
      resolveSafeHelpNavigation({
        route: "/admin/clients",
        settings_category: null,
      }, "client"),
    ).toBeNull();
    expect(
      resolveSafeHelpNavigation({
        route: "/admin/catalog",
        settings_category: null,
      }),
    ).toEqual({ to: "/admin/catalog" });
    expect(
      resolveSafeHelpNavigation({
        route: "/admin/subscriptions",
        settings_category: null,
      }),
    ).toEqual({ to: "/admin/subscriptions" });
  });

  it("allows only Client destinations for Client topics", () => {
    expect(
      resolveSafeHelpNavigation({
        route: "/client/dashboard",
        settings_category: null,
      }, "client"),
    ).toEqual({ to: "/client/dashboard" });
    expect(
      resolveSafeHelpNavigation({
        route: "/client/profile",
        settings_category: null,
      }, "client"),
    ).toEqual({ to: "/client/profile" });
    expect(
      resolveSafeHelpNavigation({
        route: "/client/help",
        settings_category: null,
      }, "client"),
    ).toEqual({ to: "/client/help" });
    expect(
      resolveSafeHelpNavigation({
        route: "/admin/clients",
        settings_category: null,
      }),
    ).toEqual({ to: "/admin/clients" });
  });

  it("rejects routes outside the navigation allowlist", () => {
    expect(
      resolveSafeHelpNavigation({
        route: "/admin/settings/profile/save",
        settings_category: null,
      }),
    ).toBeNull();
  });

  it("navigates to the regional tab within My Account", () => {
    expect(
      resolveSafeHelpNavigation({
        route: "/admin/settings",
        settings_category: "my-account",
        tab: "regional",
      }),
    ).toEqual({
      to: "/admin/settings",
      search: { category: "my-account", tab: "regional" },
    });
  });

  it("rejects locale category as it no longer exists", () => {
    expect(
      resolveSafeHelpNavigation({
        route: "/admin/settings",
        settings_category: "locale",
      }),
    ).toBeNull();
  });

  it("rejects timezone category as it no longer exists", () => {
    expect(
      resolveSafeHelpNavigation({
        route: "/admin/settings",
        settings_category: "timezone",
      }),
    ).toBeNull();
  });
});
