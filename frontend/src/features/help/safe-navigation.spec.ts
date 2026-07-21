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
        settings_category: "locale",
      }),
    ).toEqual({ to: "/admin/settings", search: { category: "locale" } });

    expect(
      resolveSafeHelpNavigation({
        route: "/admin/settings",
        settings_category: "submit-form",
      }),
    ).toBeNull();
  });

  it("allows Pro module destinations without exposing mutation routes", () => {
    expect(
      resolveSafeHelpNavigation({
        route: "/admin/clients",
        settings_category: null,
      }),
    ).toEqual({ to: "/admin/clients" });
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

  it("rejects routes outside the navigation allowlist", () => {
    expect(
      resolveSafeHelpNavigation({
        route: "/admin/settings/profile/save",
        settings_category: null,
      }),
    ).toBeNull();
  });
});
