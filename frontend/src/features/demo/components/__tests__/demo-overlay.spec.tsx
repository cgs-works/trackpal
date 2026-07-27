import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { DemoOverlay } from "../demo-overlay";

vi.mock("@/i18n", () => ({
  t: (key: string) => {
    const translations: Record<string, string> = {
      "frontend.demo.overlay.message":
        "Interaction paused. Verifying demo status…",
      "frontend.demo.overlay.retry": "Retry now",
    };
    return translations[key] ?? key;
  },
}));

describe("DemoOverlay", () => {
  it("renders an accessible retry action and pause message", () => {
    const onRetry = vi.fn();
    render(<DemoOverlay onRetry={onRetry} />);

    const overlay = screen.getByTestId("demo-overlay");
    expect(overlay).toHaveAttribute("role", "dialog");
    expect(overlay).toHaveAttribute("aria-modal", "true");
    expect(
      screen.getByText("Interaction paused. Verifying demo status…"),
    ).toBeInTheDocument();
    screen.getByRole("button", { name: "Retry now" }).click();
    expect(onRetry).toHaveBeenCalledOnce();
  });
});
