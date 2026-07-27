import { describe, expect, it, vi } from "vitest";
import { getAdminNavigationItems } from "../role-navigation";

vi.mock("@/i18n", () => ({
  t: (key: string) => key,
}));

describe("demo simulator navigation", () => {
  it("is absent unless the authenticated layout explicitly enables it", () => {
    expect(getAdminNavigationItems(false).some((item) => item.to === "/admin/demo/simulator")).toBe(false);
    expect(getAdminNavigationItems(true, true).some((item) => item.to === "/admin/demo/simulator")).toBe(false);
  });

  it("adds the simulator as a normal admin destination when enabled", () => {
    const items = getAdminNavigationItems(false, false, true);
    expect(items.map((item) => item.to)).toContain("/admin/demo/simulator");
  });
});
