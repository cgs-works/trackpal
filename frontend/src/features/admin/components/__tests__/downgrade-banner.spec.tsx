import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { DowngradeBanner } from "../downgrade-banner";

vi.mock("@/i18n", () => ({
  t: (key: string) => key,
}));

describe("DowngradeBanner", () => {
  it("explains that Pro data is preserved while automation is paused", () => {
    render(<DowngradeBanner />);

    expect(screen.getByTestId("downgrade-banner")).toBeInTheDocument();
    expect(screen.getByText("frontend.plan.downgrade_title")).toBeInTheDocument();
    expect(
      screen.getByText("frontend.plan.downgrade_description"),
    ).toBeInTheDocument();
  });
});
