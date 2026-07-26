import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { DemoOverlay } from "../demo-overlay";

vi.mock("@/i18n", () => ({
  t: (key: string) => {
    const translations: Record<string, string> = {
      "frontend.demo.overlay.message":
        "Interaction paused. Verifying demo status…",
    };
    return translations[key] ?? key;
  },
}));

describe("DemoOverlay", () => {
  it("renders accessible overlay with pause message", () => {
    render(<DemoOverlay />);

    const overlay = screen.getByTestId("demo-overlay");
    expect(overlay).toBeInTheDocument();
    expect(overlay).toHaveAttribute("role", "alert");
    expect(overlay).toHaveAttribute("aria-live", "assertive");
    expect(
      screen.getByText("Interaction paused. Verifying demo status…"),
    ).toBeInTheDocument();
  });
});
