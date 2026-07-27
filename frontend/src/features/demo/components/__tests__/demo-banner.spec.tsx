import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi, beforeEach } from "vitest";
import { DemoBanner } from "../demo-banner";

vi.mock("@/i18n", () => ({
  t: (key: string, params?: Record<string, string | number>) => {
    const translations: Record<string, string> = {
      "frontend.demo.banner.title": "Demo Account",
      "frontend.demo.banner.remaining": "{time} remaining",
      "frontend.demo.banner.browser_local": "Data is stored in this browser only.",
      "frontend.demo.banner.connectivity_warning":
        "We are having trouble verifying this demo. Your local work is preserved; retry shortly.",
      "frontend.demo.banner.workspace_recovered":
        "Your demo was updated to a safe version. Your progress and data were preserved.",
      "frontend.demo.banner.storage_unavailable":
        "Your browser has no storage available. Demo changes will not be saved.",
      "frontend.demo.banner.storage_quota_exceeded":
        "Browser storage is full. Demo changes will not be saved.",
      "frontend.demo.banner.reset": "Reset Demo Data",
      "frontend.demo.banner.reset_confirm_title": "Reset demo data?",
      "frontend.demo.banner.reset_confirm_description":
        "This will reset the demo to its initial state. Your credentials and progress will be preserved.",
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
  plan: "starter" as "starter" | "pro",
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
      consumeRecoveryNotice?: ReturnType<typeof vi.fn>;
      storageState?: ReturnType<typeof vi.fn>;
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
        consumeRecoveryNotice: vi.fn().mockReturnValue(null),
        storageState: vi.fn().mockReturnValue("available"),
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

  it("shows a localized warning after one connectivity failure", () => {
    mockAuthStore();
    render(<DemoBanner showConnectivityWarning />);

    expect(
      screen.getByText(
        "We are having trouble verifying this demo. Your local work is preserved; retry shortly.",
      ),
    ).toBeInTheDocument();
  });

  it("shows browser-local explanation", () => {
    mockAuthStore();
    render(<DemoBanner />);
    expect(
      screen.getByText(/Data is stored in this browser only/),
    ).toBeInTheDocument();
  });

  it("shows one localized recovery notice", () => {
    const recoveryNotice = vi.fn().mockReturnValue({ kind: "reset" });
    mockAuthStore({
      dataSource: {
        mode: "demo",
        workspace: {
          reset: vi.fn(),
          read: vi.fn(),
          ensure: vi.fn(),
          saveTourState: vi.fn(),
          clear: vi.fn(),
          consumeRecoveryNotice: recoveryNotice,
          storageState: vi.fn().mockReturnValue("available"),
          key: "trackpal:demo-workspace:demo-tenant-1",
        },
      },
    });
    render(<DemoBanner />);

    expect(screen.getAllByTestId("demo-workspace-recovered")).toHaveLength(1);
    expect(recoveryNotice).toHaveBeenCalledOnce();
  });

  it("shows explicit browser storage failures without backend fallback", () => {
    mockAuthStore({
      dataSource: {
        mode: "demo",
        workspace: {
          reset: vi.fn(),
          read: vi.fn(),
          ensure: vi.fn(),
          saveTourState: vi.fn(),
          clear: vi.fn(),
          consumeRecoveryNotice: vi.fn().mockReturnValue(null),
          storageState: vi.fn().mockReturnValue("quota_exceeded"),
          key: "trackpal:demo-workspace:demo-tenant-1",
        },
      },
    });
    render(<DemoBanner />);

    expect(screen.getByTestId("demo-storage-quota")).toHaveTextContent(
      "Browser storage is full. Demo changes will not be saved.",
    );
  });

  it("shows Pro label for pro plan", () => {
    mockAuthStore({
      demo: { ...activeDemoMetadata, plan: "pro" },
    });
    render(<DemoBanner />);
    expect(screen.getByText("(Pro)")).toBeInTheDocument();
  });

  it("shows countdown without a noisy live region", () => {
    mockAuthStore();
    render(<DemoBanner />);
    const countdown = screen.getByTestId("demo-countdown");
    expect(countdown).toBeInTheDocument();
    expect(countdown).toHaveTextContent("remaining");
    expect(countdown).not.toHaveAttribute("aria-live", "polite");
  });

  it("blocks reset when browser storage cannot persist changes", () => {
    mockAuthStore({
      dataSource: {
        mode: "demo",
        workspace: {
          reset: vi.fn(),
          read: vi.fn(),
          ensure: vi.fn(),
          saveTourState: vi.fn(),
          clear: vi.fn(),
          consumeRecoveryNotice: vi.fn().mockReturnValue(null),
          storageState: vi.fn().mockReturnValue("unavailable"),
          key: "trackpal:demo-workspace:demo-tenant-1",
        },
      },
    });
    render(<DemoBanner />);

    expect(screen.getByTestId("demo-reset-trigger")).toBeDisabled();
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
        "This will reset the demo to its initial state. Your credentials and progress will be preserved.",
      ),
    ).toBeInTheDocument();
  });
});
