import { render, screen } from "@testing-library/react";
import { AppSidebar } from "../app-sidebar";

describe("AppSidebar", () => {
  it("renders the TrackPal landing-page logo", () => {
    render(
      <AppSidebar
        username="operator"
        items={[]}
        onLogout={() => undefined}
      />
    );

    const logo = screen.getByRole("img", { name: "TrackPal" });

    expect(logo).toHaveAttribute("aria-label", "TrackPal");
    expect(logo.querySelector('img[src="/trackpal-dark.png"]')).toBeInTheDocument();
    expect(logo.querySelector('img[src="/trackpal-light.png"]')).toBeInTheDocument();
  });
});
