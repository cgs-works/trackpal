import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { LayoutDashboard } from "lucide-react";
import { AppSidebar, MobileSidebar } from "../app-sidebar";

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

describe("MobileSidebar", () => {
  it("opens the role navigation and restores focus after selecting a destination", async () => {
    const user = userEvent.setup();
    const onSelect = vi.fn();

    render(
      <MobileSidebar
        username="operator"
        items={[
          {
            label: "Dashboard",
            icon: <LayoutDashboard />,
            onSelect,
          },
        ]}
        onLogout={() => undefined}
      />
    );

    const trigger = screen.getByRole("button", {
      name: /toggle menu|navigation\.toggle_menu/i,
    });
    await user.click(trigger);

    expect(screen.getByRole("dialog")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Dashboard" })).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "Dashboard" }));

    expect(onSelect).toHaveBeenCalledOnce();
    await waitFor(() => expect(screen.queryByRole("dialog")).not.toBeInTheDocument());
    expect(trigger).toHaveFocus();
  });
});
