import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { ProfilePage } from "../profile-page";
import { useAuthStore } from "@/store/auth";
import type { ClientProfile } from "../../services/client-dashboard-api";

const getProfile = vi.hoisted(() => vi.fn());
const changePassword = vi.hoisted(() => vi.fn());

vi.mock("../../services/client-dashboard-api", () => ({
  getProfile,
  changePassword,
}));

vi.mock("@/i18n", () => ({
  t: (key: string, params?: Record<string, string | number>) =>
    params ? `${key}:${JSON.stringify(params)}` : key,
  getLocale: () => "en",
}));

vi.mock("sonner", () => ({
  toast: { success: vi.fn(), error: vi.fn() },
}));

vi.mock("@tanstack/react-router", () => ({
  Navigate: () => null,
}));

const PROFILE: ClientProfile = {
  role: "client",
  username: "client_demo",
  name: null,
  full_name: "Client Demo",
  tenant_id: "tenant-1",
  tenant_name: "Provider",
  client_prefix: "demo",
  locale: "es",
  email: null,
  phone: null,
  is_active: true,
  created_at: "2026-01-01T00:00:00.000Z",
  updated_at: "2026-01-01T00:00:00.000Z",
};

beforeEach(() => {
  localStorage.clear();
  useAuthStore.setState({
    isAuthenticated: true,
    role: "client",
  });
  getProfile.mockReset();
  changePassword.mockReset();
  vi.restoreAllMocks();
});

describe("ProfilePage client profile", () => {
  it("renders the profile information once loaded", async () => {
    getProfile.mockResolvedValue(PROFILE);

    render(<ProfilePage />);

    expect(await screen.findByText("Client Demo")).toBeInTheDocument();
    expect(screen.getByText("frontend.dashboard.client.profile_info")).toBeInTheDocument();
    expect(screen.getByText("frontend.dashboard.client.full_name")).toBeInTheDocument();
    expect(screen.getByText("frontend.dashboard.client.username")).toBeInTheDocument();
    expect(screen.getByText("frontend.dashboard.client.status")).toBeInTheDocument();
    expect(
      screen.getByText("frontend.dashboard.client.status_active"),
    ).toBeInTheDocument();
  });
});

describe("ProfilePage client load error", () => {
  it("shows a localized error state and retries", async () => {
    getProfile.mockRejectedValueOnce(new Error("boom"));

    render(<ProfilePage />);

    expect(
      await screen.findByText("frontend.profile.load_error"),
    ).toBeInTheDocument();
    expect(screen.getByText("frontend.common.retry")).toBeInTheDocument();

    getProfile.mockResolvedValueOnce(PROFILE);
    await userEvent.click(screen.getByText("frontend.common.retry"));

    expect(await screen.findByText("Client Demo")).toBeInTheDocument();
  });
});
