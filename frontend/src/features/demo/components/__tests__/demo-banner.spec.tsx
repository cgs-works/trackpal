import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi, beforeEach } from "vitest";
import { DemoBanner } from "../demo-banner";
import { useAuthStore } from "@/store/auth";

vi.mock("@/i18n", () => ({
  t: (key: string, params?: Record<string, string | number>) => {
    const translations: Record<string, string> = {
      "frontend.demo.banner.title": "Demo Account",
      "frontend.demo.banner.remaining": "{time} remaining",
      "frontend.demo.banner.browser_local": "Data is stored in this browser only.",
      "frontend.demo.banner.reset": "Reset Demo Data",
      "frontend.demo.banner.reset_confirm_title": "Reset demo data?",
      "frontend.demo.banner.reset_confirm_description":
        "This restores the demo baseline. Credentials, expiration, and tour progress are preserved.",
      "frontend.demo.banner.reset_confirm_action": "Reset data",
      "frontend.demo.banner.expired": "Expired",
      "frontend.master.demos.starter": "Starter",
      "frontend.master.demos.pro": "Pro",
      "frontend.master.demos.cancel": "Cancel",
      "frontend.master.demos.hours": "{hours}h",
      "frontend.master.demos.minutes": "{minutes}m",
    };
    let value = translations[key] ?? key;
    if (params) {
      for (const [k, v] of Object.entries(params)) {
        value = value.replace(new RegExp(`\\{${k}\\}`, "g"), String(v));
      }
    }
    return value;
  },
}));

const { mockGetState, mockUseAuthStore } = vi.hoisted(() => ({
  mockGetState: vi.fn(),
  mockUseAuthStore: vi.fn(),
}));

vi.mock("@/store/auth", () => ({
  useAuthStore: Object.assign(mockUseAuthStore, {
    getState: mockGetState,
    setState: vi.fn(),
    subscribe: vi.fn(),
  }),
}));

const activeDemoMetadata = {
  tenantId: "demo-tenant-1",
  name: "Test Demo",
  plan: "starter" as const,
  status: "active" as const,
  activatedAt: "2026-07-25T10:00:00Z",
  expiresAt: "2026-07-27T10:00:00Z",
  credentialVersion: 1,
  serverTime: "2026-07-25T10:00:00Z",
};

const pendingDemoMetadata = {
  ...activeDemoMetadata,
  status: "pending" as const,
  activatedAt: null,
  expiresAt: null,
};

interface MockAuthState {
  token: string | null;
  refreshToken: string | null;
  user: { id: string; role: string; username: string } | null;
  activeTenantId: string | null;
  tenantPlan: "starter" | "pro" | null;
  demo: typeof activeDemoMetadata | typeof pendingDemoMetadata | null;
  authOutcome: string;
  isAuthenticated: boolean;
  role: string | null;
  username: string;
  dataSource: {
    mode: "demo" | "production";
    workspace: {
      reset: ReturnType<typeof vi.fn>;
      read: ReturnType<typeof vi.fn>;
      ensure: ReturnType<typeof vi.fn>;
      saveTourState: ReturnType<typeof vi.fn>;
      clear: ReturnType<typeof vi.fn>;
      key: string;
    } | null;
  };
}

function mockAuthStore(overrides: Partial<MockAuthState> = {}) {
  const defaultState: MockAuthState = {
    token: "demo-access",
    refreshToken: "demo-refresh",
    user: { id: "u1", role: "tenant", username: "demo-user" },
    activeTenantId: "demo-tenant-1",
    tenantPlan: "starter",
    demo: activeDemoMetadata,
    authOutcome: "authenticated",
    isAuthenticated: true,
    role: "tenant",
    username: "demo-user",
    dataSource: {
      mode: "demo",
      workspace: {
        reset: vi.fn(),
        read: vi.fn(),
        ensure: vi.fn(),
        saveTourState: vi.fn(),
        clear: vi.fn(),
        key: "trackpal:demo-workspace:demo-tenant-1",
      },
    },
    ...overrides,
  };

  mockGetState.mockReturnValue(defaultState);
  mockUseAuthStore.mockImplementation(
    (selector: (state: MockAuthState) => unknown) => selector(defaultState),
  );
}

beforeEach(() => {
  vi.clearAllMocks();
});

describe("DemoBanner", () => {
  it("renders when demo is active", () => {
    mockAuthStore();
    render(<DemoBanner />);

    expect(screen.getByTestId("demo-banner")).toBeInTheDocument();
    expect(screen.getByText("Demo Account")).toBeInTheDocument();
    expect(screen.getByText("(Starter)")).toBeInTheDocument();
  });

  it("does not render when demo is null", () => {
    mockAuthStore({ demo: null });
    const { container } = render(<DemoBanner />);
    expect(container.firstChild).toBeNull();
  });

  it("does not render when demo is pending", () => {
    mockAuthStore({ demo: pendingDemoMetadata });
    const { container } = render(<DemoBanner />);
    expect(container.firstChild).toBeNull();
  });

  it("shows browser-local explanation", () => {
    mockAuthStore();
    render(<DemoBanner />);
    expect(
      screen.getByText(/Data is stored in this browser only/),
    ).toBeInTheDocument();
  });

  it("shows Pro label for pro plan", () => {
    mockAuthStore({
      demo: { ...activeDemoMetadata, plan: "pro" },
    });
    render(<DemoBanner />);
    expect(screen.getByText("(Pro)")).toBeInTheDocument();
  });

  it("shows countdown with remaining time", () => {
    mockAuthStore();
    render(<DemoBanner />);
    expect(screen.getByTestId("demo-countdown")).toBeInTheDocument();
    expect(screen.getByTestId("demo-countdown")).toHaveTextContent("remaining");
  });

  it("shows reset button", () => {
    mockAuthStore();
    render(<DemoBanner />);
    expect(screen.getByTestId("demo-reset-trigger")).toBeInTheDocument();
    expect(screen.getByText("Reset Demo Data")).toBeInTheDocument();
  });

  it("opens confirmation dialog on reset click", () => {
    mockAuthStore();
    render(<DemoBanner />);

    fireEvent.click(screen.getByTestId("demo-reset-trigger"));
    expect(screen.getByText("Reset demo data?")).toBeInTheDocument();
    expect(
      screen.getByText(
        "This restores the demo baseline. Credentials, expiration, and tour progress are preserved.",
      ),
    ).toBeInTheDocument();
  });
});
