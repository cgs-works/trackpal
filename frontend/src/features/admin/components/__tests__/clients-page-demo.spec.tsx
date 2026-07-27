import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { ClientsPage } from "../clients-page";
import { createDataSource } from "@/lib/data-source";
import { useAuthStore } from "@/store/auth";
import { useCatalogStore } from "@/store/catalog";
import api from "@/lib/api";
import { toast } from "sonner";

vi.mock("@/i18n", () => ({
  t: (key: string, params?: Record<string, string | number>) =>
    params ? `${key}:${JSON.stringify(params)}` : key,
}));

vi.mock("@tanstack/react-router", () => ({
  useNavigate: () => vi.fn(),
}));

const metadata = {
  tenantId: "render-demo",
  name: "Rendered Demo",
  plan: "pro" as const,
  status: "active" as const,
  activatedAt: "2026-07-24T12:00:00.000Z",
  expiresAt: "2026-07-26T12:00:00.000Z",
  credentialVersion: 1,
  serverTime: "2026-07-25T12:00:00.000Z",
};

beforeEach(() => {
  localStorage.clear();
  useCatalogStore.getState().clearAll();
  useAuthStore.setState({
    dataSource: createDataSource({
      tenantId: metadata.tenantId,
      tenantPlan: "pro",
      demo: metadata,
    }),
  });
  vi.restoreAllMocks();
});

describe("ClientsPage Demo rendering", () => {
  it("renders the local baseline with accessible filtering and no API request", async () => {
    const getSpy = vi.spyOn(api, "get");
    render(<ClientsPage />);

    await waitFor(() => {
      expect(screen.getAllByText("Avery Stone")).toHaveLength(2);
    });
    expect(screen.getByRole("combobox", { name: "frontend.clients.status_filter" })).toBeInTheDocument();
    expect(screen.getByPlaceholderText("frontend.clients.search_placeholder")).toBeInTheDocument();
    expect(getSpy).not.toHaveBeenCalled();
  });

  it("filters the current workspace by active status", async () => {
    const user = userEvent.setup();
    render(<ClientsPage />);
    await waitFor(() => {
      expect(screen.getAllByText("Avery Stone")).toHaveLength(2);
    });

    await user.selectOptions(
      screen.getByRole("combobox", { name: "frontend.clients.status_filter" }),
      "inactive",
    );

    await waitFor(() => {
      expect(screen.getAllByText("Priya Nair")).toHaveLength(2);
      expect(screen.queryAllByText("Avery Stone")).toHaveLength(0);
    });
  });
  it("shows a live relationship preview before cascading client deletion", async () => {
    const user = userEvent.setup();
    const source = useAuthStore.getState().dataSource;
    const mina = (await source.crud.clients.list()).find((client) => client.full_name === "Mina Duarte")!;
    await source.crud.clients.deactivate(mina.id);

    render(<ClientsPage />);
    await waitFor(() => expect(screen.getAllByText("Mina Duarte")).toHaveLength(2));
    const row = screen.getAllByText("Mina Duarte")[0].closest("tr");
    await user.click(within(row!).getByRole("button", { name: "frontend.clients.delete" }));

    const dialog = await screen.findByRole("alertdialog");
    await waitFor(() => {
      expect(within(dialog).getAllByText("1").length).toBeGreaterThan(0);
      expect(within(dialog).getAllByText("2").length).toBeGreaterThan(0);
    });
    await user.click(within(dialog).getByRole("button", { name: "frontend.clients.delete" }));
    await waitFor(() => expect(screen.queryAllByText("Mina Duarte")).toHaveLength(0));
  });

  it("performs create, edit, lifecycle, delete, and pagination locally", async () => {
    const user = userEvent.setup();
    const getSpy = vi.spyOn(api, "get");
    const successSpy = vi.spyOn(toast, "success");
    const clients = useAuthStore.getState().dataSource.crud.clients;
    for (let index = 0; index < 6; index += 1) {
      await clients.create({
        full_name: `Extra Client ${index}`,
        local_username: `extra_client_${index}`,
        phone: `+1 (415) 555-27${String(index).padStart(2, "0")}`,
        password: "not-persisted",
      });
    }

    render(<ClientsPage />);
    await waitFor(() => expect(screen.getAllByText("Avery Stone")).toHaveLength(2));
    expect(screen.getByRole("button", { name: "frontend.clients.next" })).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "frontend.clients.create" }));
    await user.type(screen.getByLabelText("frontend.profile.full_name"), "Nora Example");
    await user.type(screen.getByLabelText("frontend.dashboard.client.local_user"), "nora_example");
    await user.type(screen.getByLabelText("frontend.profile.phone"), "+1 (415) 555-2676");
    await user.type(screen.getByLabelText("frontend.clients.password"), "not-persisted");
    await user.click(screen.getByRole("button", { name: "frontend.common.save" }));
    expect(successSpy).toHaveBeenCalledWith(
      'frontend.clients.created:{"login":"demo_nora_example"}',
    );
    await user.click(screen.getByRole("button", { name: "frontend.clients.next" }));
    await waitFor(() => expect(screen.getAllByText("Nora Example")).toHaveLength(2));

    const noraRow = screen.getAllByText("Nora Example")[0].closest("tr");
    expect(noraRow).not.toBeNull();
    await user.click(within(noraRow!).getByRole("button", { name: "frontend.clients.edit" }));
    const fullNameInput = screen.getByLabelText("frontend.profile.full_name");
    await user.clear(fullNameInput);
    await user.type(fullNameInput, "Nora Updated");
    await user.click(screen.getByRole("button", { name: "frontend.common.save" }));
    expect(successSpy).toHaveBeenLastCalledWith(
      'frontend.clients.updated:{"login":"demo_nora_example"}',
    );
    await waitFor(async () => {
      const updated = await clients.list();
      expect(updated.some((client) => client.full_name === "Nora Updated")).toBe(true);
    });
    await user.click(screen.getByRole("button", { name: "frontend.clients.previous" }));
    await waitFor(() => expect(screen.getAllByText("Avery Stone")).toHaveLength(2));
    const averyRow = screen.getAllByText("Avery Stone")[0].closest("tr");
    await user.click(within(averyRow!).getByRole("button", { name: "frontend.clients.deactivate" }));
    await waitFor(() => {
      const updatedAveryRow = screen.getAllByText("Avery Stone")[0].closest("tr");
      expect(within(updatedAveryRow!).getByText("frontend.dashboard.client.status_inactive")).toBeInTheDocument();
    });

    const jonRow = screen.getAllByText("Jon Bell")[0].closest("tr");
    await user.click(within(jonRow!).getByRole("button", { name: "frontend.clients.delete" }));
    const dialog = screen.getByRole("alertdialog");
    await user.click(within(dialog).getByRole("button", { name: "frontend.clients.delete" }));
    await waitFor(() => expect(screen.queryAllByText("Jon Bell")).toHaveLength(0));
    expect(getSpy).not.toHaveBeenCalled();
  }, 20000);
});
