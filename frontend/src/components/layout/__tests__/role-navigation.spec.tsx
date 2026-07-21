import {
  createSidebarItems,
  getAdminNavigationItems,
  getClientNavigationItems,
} from "../role-navigation";

describe("role navigation model", () => {
  it("limits Starter Tenant Admins to the non-Pro destinations", () => {
    const items = getAdminNavigationItems(false);

    expect(items.map((item) => item.to)).toEqual([
      "/admin/dashboard",
      "/admin/settings",
    ]);
  });

  it("keeps all Tenant Admin destinations in the existing order for Pro access", () => {
    const items = getAdminNavigationItems(true);

    expect(items.map((item) => item.to)).toEqual([
      "/admin/dashboard",
      "/admin/clients",
      "/admin/catalog",
      "/admin/subscriptions",
      "/admin/settings",
    ]);
  });

  it("adds Help only when the private Help release gate is enabled", () => {
    expect(getAdminNavigationItems(false).map((item) => item.to)).not.toContain(
      "/admin/help",
    );
    expect(getAdminNavigationItems(false, true).map((item) => item.to)).toEqual([
      "/admin/dashboard",
      "/admin/settings",
      "/admin/help",
    ]);
  });

  it("keeps the Client destinations limited to Dashboard and Profile", () => {
    const items = getClientNavigationItems();

    expect(items.map((item) => item.to)).toEqual([
      "/client/dashboard",
      "/client/profile",
    ]);
  });

  it("marks the matching route active while preserving nested admin routes", () => {
    const items = createSidebarItems(
      getAdminNavigationItems(true),
      "/admin/catalog/plan-1",
    );

    expect(items.find((item) => item.to === "/admin/catalog")?.active).toBe(true);
    expect(items.find((item) => item.to === "/admin/dashboard")?.active).toBe(false);
  });

  it("uses exact active matching for Client destinations", () => {
    const items = createSidebarItems(
      getClientNavigationItems(),
      "/client/profile",
    );

    expect(items[0]?.active).toBe(false);
    expect(items[1]?.active).toBe(true);
  });
});
