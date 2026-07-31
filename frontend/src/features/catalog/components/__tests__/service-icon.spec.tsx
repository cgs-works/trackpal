import { render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { ServiceIcon } from "../service-icon";

const loadIcon = vi.hoisted(() => vi.fn());
vi.mock("@iconify/react", () => ({
  loadIcon,
  Icon: ({ icon }: { icon: unknown }) => (
    <span data-testid="iconify-icon">{JSON.stringify(icon)}</span>
  ),
}));

describe("ServiceIcon", () => {
  beforeEach(() => {
    loadIcon.mockReset();
    vi.spyOn(console, "error").mockImplementation(() => {});
  });

  it("renders loaded Iconify data", async () => {
    loadIcon.mockResolvedValue({ body: '<path fill="#e50914" />', width: 24, height: 24 });
    render(<ServiceIcon icon="simple-icons:netflix" label="Netflix" />);
    expect(await screen.findByTestId("iconify-icon")).toHaveTextContent("#e50914");
    expect(screen.getByRole("img", { name: "Netflix" })).toBeInTheDocument();
  });

  it("uses the generic fallback for null and load failures", async () => {
    const { rerender } = render(<ServiceIcon icon={null} label="Unknown" />);
    expect(screen.getByTestId("service-icon-fallback")).toBeInTheDocument();

    loadIcon.mockRejectedValue(new Error("offline"));
    rerender(<ServiceIcon icon="simple-icons:missing" label="Missing" />);
    await waitFor(() =>
      expect(screen.getByTestId("service-icon-fallback")).toBeInTheDocument(),
    );
  });
});
