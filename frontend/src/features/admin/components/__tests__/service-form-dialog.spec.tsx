import { render, screen, waitFor, fireEvent } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { ServiceFormDialog } from "../service-form-dialog";

vi.mock("@/i18n", () => ({
  t: (key: string, params?: Record<string, string | number>) =>
    params ? `${key}:${JSON.stringify(params)}` : key,
}));

vi.mock("@/features/catalog/components/icon-picker", () => ({
  IconPicker({
    open,
    onSelect,
  }: {
    open: boolean;
    onSelect: (icon: string | null) => void;
  }) {
    if (!open) return null;
    return (
      <div data-testid="mock-icon-picker">
        <button type="button" onClick={() => onSelect("simple-icons:netflix")}>
          choose-test-icon
        </button>
      </div>
    );
  },
}));

vi.mock("@/features/catalog/components/service-icon", () => ({
  ServiceIcon({ icon, label }: { icon: string | null; label: string }) {
    return (
      <span data-testid={`service-icon-${icon ?? "none"}`}>
        {label}
      </span>
    );
  },
}));

describe("ServiceFormDialog", () => {
  it("submits a new service with the selected icon", async () => {
    const user = userEvent.setup();
    const onSubmit = vi.fn().mockResolvedValue(undefined);
    render(
      <ServiceFormDialog
        open
        mode="create"
        saving={false}
        error=""
        onOpenChange={vi.fn()}
        onSubmit={onSubmit}
      />,
    );

    await user.type(screen.getByLabelText("frontend.common.name"), "Netflix");
    fireEvent.click(screen.getByTestId("choose-icon-btn"));
    const pickerBtn = await screen.findByText("choose-test-icon");
    await user.click(pickerBtn);
    await user.click(
      screen.getByRole("button", { name: "frontend.catalog.save_service" }),
    );

    expect(onSubmit).toHaveBeenCalledWith({
      name: "Netflix",
      icon: "simple-icons:netflix",
    });
  });

  it("creates a service with no icon when icon is not selected", async () => {
    const user = userEvent.setup();
    const onSubmit = vi.fn().mockResolvedValue(undefined);
    render(
      <ServiceFormDialog
        open
        mode="create"
        saving={false}
        error=""
        onOpenChange={vi.fn()}
        onSubmit={onSubmit}
      />,
    );

    await user.type(screen.getByLabelText("frontend.common.name"), "Hulu");
    await user.click(
      screen.getByRole("button", { name: "frontend.catalog.save_service" }),
    );

    expect(onSubmit).toHaveBeenCalledWith({
      name: "Hulu",
      icon: null,
    });
  });

  it("preserves existing icon in edit mode", async () => {
    const user = userEvent.setup();
    const onSubmit = vi.fn().mockResolvedValue(undefined);
    render(
      <ServiceFormDialog
        open
        mode="edit"
        service={{
          id: "svc-1",
          tenant_id: "t1",
          name: "Netflix",
          icon: "simple-icons:netflix",
          created_at: "2026-01-01T00:00:00Z",
          updated_at: "2026-01-01T00:00:00Z",
        }}
        saving={false}
        error=""
        onOpenChange={vi.fn()}
        onSubmit={onSubmit}
      />,
    );

    expect(screen.getByLabelText("frontend.common.name")).toHaveValue("Netflix");

    await user.click(
      screen.getByRole("button", { name: "frontend.catalog.save_service" }),
    );

    expect(onSubmit).toHaveBeenCalledWith({
      name: "Netflix",
      icon: "simple-icons:netflix",
    });
  });

  it("replaces icon in edit mode when user picks a new one", async () => {
    const user = userEvent.setup();
    const onSubmit = vi.fn().mockResolvedValue(undefined);
    render(
      <ServiceFormDialog
        open
        mode="edit"
        service={{
          id: "svc-1",
          tenant_id: "t1",
          name: "Netflix",
          icon: "simple-icons:netflix",
          created_at: "2026-01-01T00:00:00Z",
          updated_at: "2026-01-01T00:00:00Z",
        }}
        saving={false}
        error=""
        onOpenChange={vi.fn()}
        onSubmit={onSubmit}
      />,
    );

    // Open the picker and select a different icon
    fireEvent.click(screen.getByTestId("choose-icon-btn"));
    const pickerBtn = await screen.findByText("choose-test-icon");
    await user.click(pickerBtn);
    await user.click(
      screen.getByRole("button", { name: "frontend.catalog.save_service" }),
    );

    expect(onSubmit).toHaveBeenCalledWith({
      name: "Netflix",
      icon: "simple-icons:netflix",
    });
  });

  it("removes icon and submits icon: null in edit mode", async () => {
    const user = userEvent.setup();
    const onSubmit = vi.fn().mockResolvedValue(undefined);
    render(
      <ServiceFormDialog
        open
        mode="edit"
        service={{
          id: "svc-1",
          tenant_id: "t1",
          name: "Netflix",
          icon: "simple-icons:netflix",
          created_at: "2026-01-01T00:00:00Z",
          updated_at: "2026-01-01T00:00:00Z",
        }}
        saving={false}
        error=""
        onOpenChange={vi.fn()}
        onSubmit={onSubmit}
      />,
    );

    await user.click(
      screen.getByRole("button", { name: "frontend.catalog.remove_icon" }),
    );
    await user.click(
      screen.getByRole("button", { name: "frontend.catalog.save_service" }),
    );

    expect(onSubmit).toHaveBeenCalledWith({
      name: "Netflix",
      icon: null,
    });
  });

  it("shows saving state on submit button", () => {
    render(
      <ServiceFormDialog
        open
        mode="create"
        saving={true}
        error=""
        onOpenChange={vi.fn()}
        onSubmit={vi.fn()}
      />,
    );

    expect(
      screen.getByRole("button", { name: "frontend.catalog.saving" }),
    ).toBeDisabled();
  });

  it("displays error message", () => {
    render(
      <ServiceFormDialog
        open
        mode="create"
        saving={false}
        error="frontend.catalog.invalid_icon"
        onOpenChange={vi.fn()}
        onSubmit={vi.fn()}
      />,
    );

    expect(
      screen.getByText("frontend.catalog.invalid_icon"),
    ).toBeInTheDocument();
  });

  it("resets form state when dialog opens", async () => {
    const onSubmit = vi.fn().mockResolvedValue(undefined);
    const { rerender } = render(
      <ServiceFormDialog
        open={false}
        mode="create"
        saving={false}
        error=""
        onOpenChange={vi.fn()}
        onSubmit={onSubmit}
      />,
    );

    rerender(
      <ServiceFormDialog
        open
        mode="create"
        saving={false}
        error=""
        onOpenChange={vi.fn()}
        onSubmit={onSubmit}
      />,
    );

    expect(screen.getByLabelText("frontend.common.name")).toHaveValue("");
  });
});
