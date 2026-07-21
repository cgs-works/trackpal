import { describe, expect, it } from "vitest";
import { findActiveHelpTarget, HELP_TARGETS } from "./help-targets";

describe("findActiveHelpTarget", () => {
  it("prefers the most specific semantic target on the current screen", () => {
    const root = document.createElement("main");
    root.innerHTML = `
      <section data-help-id="admin.settings">
        <div data-help-id="admin.settings.profile"></div>
      </section>
    `;

    expect(findActiveHelpTarget(root)).toBe("admin.settings.profile");
  });

  it("keeps Pro module targets stable and semantic", () => {
    expect(HELP_TARGETS.clients).toBe("admin.clients");
    expect(HELP_TARGETS.catalog).toBe("admin.catalog");
    expect(HELP_TARGETS.subscriptions).toBe("admin.subscriptions");

    const root = document.createElement("main");
    root.innerHTML = `
      <div data-help-id="admin.clients"></div>
      <div data-help-id="admin.catalog"></div>
      <div data-help-id="admin.subscriptions"></div>
    `;

    expect(findActiveHelpTarget(root)).toBe("admin.subscriptions");
  });

  it("keeps Client targets separate from Tenant Admin targets", () => {
    expect(HELP_TARGETS.clientDashboard).toBe("client.dashboard");
    expect(HELP_TARGETS.clientProfile).toBe("client.profile");
    expect(HELP_TARGETS.clientSubscriptions).toBe("client.subscriptions");
    expect(HELP_TARGETS.clientPassword).toBe("client.password");
  });

  it("ignores hidden targets", () => {
    const root = document.createElement("main");
    root.innerHTML = `
      <div data-help-id="admin.settings.password" hidden></div>
      <div data-help-id="admin.dashboard"></div>
    `;

    expect(findActiveHelpTarget(root)).toBe("admin.dashboard");
  });
});
