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

  it("clears previous icon data when prop changes to new icon", async () => {
    // Load first icon successfully
    loadIcon.mockResolvedValue({ body: '<path fill="#e50914" />', width: 24, height: 24 });
    const { rerender } = render(<ServiceIcon icon="simple-icons:netflix" label="Netflix" />);
    await screen.findByTestId("iconify-icon");

    // Now change to a new icon — but make it never resolve (simulate slow load)
    let resolveSecondIcon: (v: unknown) => void;
    loadIcon.mockImplementation(
      () => new Promise((resolve) => { resolveSecondIcon = resolve; }),
    );
    rerender(<ServiceIcon icon="simple-icons:github" label="GitHub" />);

    // While the new icon is loading, the OLD icon data should NOT be shown.
    // The component should show the fallback, not the stale Netflix data.
    expect(screen.queryByTestId("iconify-icon")).not.toBeInTheDocument();
    expect(screen.getByTestId("service-icon-fallback")).toBeInTheDocument();

    // Clean up: resolve the pending promise so the test exits cleanly
    resolveSecondIcon!({ body: '<path fill="#fff" />', width: 24, height: 24 });
  });

  it("rejects invalid icon references in parseIconReference", async () => {
    const { parseIconReference } = await import(
      "../../services/icon-reference"
    );

    // Empty name after colon
    expect(parseIconReference("simple-icons:")).toBeNull();
    // Empty prefix before colon
    expect(parseIconReference(":netflix")).toBeNull();
    // Uppercase letters
    expect(parseIconReference("Simple-Icons:Netflix")).toBeNull();
    // No colon separator
    expect(parseIconReference("netflix")).toBeNull();
    // Empty string
    expect(parseIconReference("")).toBeNull();
    // null / undefined
    expect(parseIconReference(null)).toBeNull();
    expect(parseIconReference(undefined)).toBeNull();
  });
});
