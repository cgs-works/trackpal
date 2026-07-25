import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { DemosTab } from "../demos-tab";
import type { DemoTenant } from "../../services/demo-api";
import { createDemo, deleteDemo, fetchDemos, replaceDemoCredentials } from "../../services/demo-api";

vi.mock("@/i18n", () => ({
  t: (key: string, params?: Record<string, string | number>) =>
    params ? `${key}:${JSON.stringify(params)}` : key,
  getLocale: () => "en",
}));

vi.mock("../../services/demo-api", () => ({
  fetchDemos: vi.fn(),
  createDemo: vi.fn(),
  replaceDemoCredentials: vi.fn(),
  deleteDemo: vi.fn(),
}));

const demos: DemoTenant[] = [
  {
    id: "pending-id",
    name: "Pending Demo",
    plan: "starter",
    status: "pending",
    username: "pending_demo",
    created_at: "2026-07-24T12:00:00Z",
    demo_activated_at: null,
    demo_expires_at: null,
    server_time: "2026-07-25T12:00:00Z",
    remaining_seconds: null,
  },
  {
    id: "active-id",
    name: "Active Demo",
    plan: "pro",
    status: "active",
    username: "active_demo",
    created_at: "2026-07-24T12:00:00Z",
    demo_activated_at: "2026-07-24T13:00:00Z",
    demo_expires_at: "2026-07-26T13:00:00Z",
    server_time: "2026-07-25T12:00:00Z",
    remaining_seconds: 90000,
  },
  {
    id: "expired-id",
    name: "Expired Demo",
    plan: "starter",
    status: "expired",
    username: "expired_demo",
    created_at: "2026-07-20T12:00:00Z",
    demo_activated_at: "2026-07-20T13:00:00Z",
    demo_expires_at: "2026-07-22T13:00:00Z",
    server_time: "2026-07-25T12:00:00Z",
    remaining_seconds: null,
  },
];

const mockedFetchDemos = vi.mocked(fetchDemos);
const mockedCreateDemo = vi.mocked(createDemo);
const mockedReplaceDemoCredentials = vi.mocked(replaceDemoCredentials);
const mockedDeleteDemo = vi.mocked(deleteDemo);

beforeEach(() => {
  vi.clearAllMocks();
  mockedFetchDemos.mockResolvedValue(demos);
});

describe("DemosTab", () => {
  it("renders loading and error states with retry", async () => {
    const promiseWithResolvers = (Promise as unknown as {
      withResolvers<T>(): { promise: Promise<T>; resolve: (value: T) => void };
    }).withResolvers;
    const { promise, resolve } = promiseWithResolvers.bind(Promise)<DemoTenant[]>();
    mockedFetchDemos.mockReturnValueOnce(promise);

    render(<DemosTab />);
    expect(screen.getByText("frontend.master.demos.loading")).toBeInTheDocument();

    resolve(demos);
    await waitFor(() => expect(screen.getAllByText("Pending Demo")[0]).toBeInTheDocument());

    mockedFetchDemos.mockRejectedValueOnce(new Error("network"));
    await userEvent.click(screen.getByRole("button", { name: "frontend.master.demos.refresh" }));
    expect(await screen.findByText("frontend.master.demos.error_load")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "frontend.master.demos.retry" })).toBeInTheDocument();
  });

  it("filters lifecycle rows without exposing workspace telemetry", async () => {
    render(<DemosTab />);

    await waitFor(() => expect(screen.getAllByText("Active Demo")[0]).toBeInTheDocument());
    expect(screen.getAllByText("frontend.master.demos.status_pending").length).toBeGreaterThan(0);
    expect(screen.getAllByText("frontend.master.demos.status_active").length).toBeGreaterThan(0);
    expect(screen.getAllByText("frontend.master.demos.status_expired").length).toBeGreaterThan(0);
    expect(screen.getAllByText(/frontend\.master\.demos\.expires/).length).toBeGreaterThan(0);
    expect(screen.queryByText(/last seen|usage|activity|workspace/i)).not.toBeInTheDocument();

    const search = screen.getByRole("searchbox", { name: "frontend.master.demos.search_label" });
    await userEvent.type(search, "expired");
    expect(screen.getAllByText("Expired Demo").length).toBeGreaterThan(0);
    expect(screen.queryAllByText("Active Demo")).toHaveLength(0);
    expect(screen.queryAllByText("Pending Demo")).toHaveLength(0);
  });

  it("creates demos and reveals copyable credentials only once", async () => {
    const created = {
      ...demos[0],
      id: "created-id",
      name: "New Demo",
      username: "new_demo",
      plain_password: "once-password",
    };
    mockedCreateDemo.mockResolvedValue(created);

    render(<DemosTab />);
    await waitFor(() => expect(screen.getAllByText("Pending Demo")[0]).toBeInTheDocument());
    await userEvent.click(screen.getByRole("button", { name: "frontend.master.demos.create" }));

    expect(screen.getByRole("dialog")).toBeInTheDocument();
    expect(screen.getByLabelText("frontend.master.demos.name_label")).toBeInTheDocument();
    expect(screen.getByLabelText("frontend.master.demos.plan_label")).toBeInTheDocument();
    expect(screen.queryByLabelText("frontend.master.demos.username_label")).not.toBeInTheDocument();
    expect(screen.getAllByText("frontend.master.demos.starter").length).toBeGreaterThan(0);

    await userEvent.type(screen.getByLabelText("frontend.master.demos.name_label"), "New Demo");
    await userEvent.click(screen.getByRole("button", { name: "frontend.master.demos.submit_create" }));

    expect(await screen.findByText("once-password")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "frontend.master.demos.copy_username" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "frontend.master.demos.copy_password" })).toBeInTheDocument();
    const writeText = vi.fn().mockResolvedValue(undefined);
    Object.defineProperty(navigator, "clipboard", {
      configurable: true,
      value: { writeText },
    });
    await userEvent.click(screen.getByRole("button", { name: "frontend.master.demos.copy_password" }));
    expect(writeText).toHaveBeenCalledWith("once-password");
    await userEvent.click(screen.getByRole("button", { name: "frontend.master.demos.dismiss_credentials" }));
    expect(screen.queryByText("once-password")).not.toBeInTheDocument();
  });

  it("allows replacement for pending and active demos but not expired demos", async () => {
    mockedReplaceDemoCredentials.mockResolvedValue({ ...demos[1], plain_password: "replacement" });

    render(<DemosTab />);
    await waitFor(() => expect(screen.getAllByText("Active Demo")[0]).toBeInTheDocument());

    expect(screen.getAllByRole("button", { name: /replace_credentials.*Pending Demo/i })[0]).toBeEnabled();
    expect(screen.getAllByRole("button", { name: /replace_credentials.*Active Demo/i })[0]).toBeEnabled();
    expect(screen.getAllByRole("button", { name: /replace_credentials.*Expired Demo/i })[0]).toBeDisabled();

    await userEvent.click(screen.getAllByRole("button", { name: /replace_credentials.*Active Demo/i })[0]);
    expect(await screen.findByText("replacement")).toBeInTheDocument();
  });

  it("confirms deletion for expired demos and refreshes the list", async () => {
    mockedDeleteDemo.mockResolvedValue(undefined);

    render(<DemosTab />);
    await waitFor(() => expect(screen.getAllByText("Expired Demo")[0]).toBeInTheDocument());
    await userEvent.click(screen.getAllByRole("button", { name: /delete.*Expired Demo/i })[0]);
    expect(screen.getByRole("alertdialog")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "frontend.master.demos.confirm_delete" }));

    await waitFor(() => expect(mockedDeleteDemo).toHaveBeenCalledWith("expired-id"));
    expect(mockedFetchDemos).toHaveBeenCalledTimes(2);
  });

  it("renders a mobile-friendly list alongside the desktop table", async () => {
    render(<DemosTab />);
    await waitFor(() => expect(screen.getAllByText("Pending Demo")[0]).toBeInTheDocument());
    expect(screen.getByTestId("demo-mobile-list")).toHaveClass("md:hidden");
  });
});
