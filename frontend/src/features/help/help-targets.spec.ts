import { describe, expect, it } from "vitest";
import { findActiveHelpTarget } from "./help-targets";

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

  it("ignores hidden targets", () => {
    const root = document.createElement("main");
    root.innerHTML = `
      <div data-help-id="admin.settings.password" hidden></div>
      <div data-help-id="admin.dashboard"></div>
    `;

    expect(findActiveHelpTarget(root)).toBe("admin.dashboard");
  });
});
