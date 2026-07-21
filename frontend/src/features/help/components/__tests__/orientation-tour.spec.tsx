import { createElement, type ComponentType } from "react";
import { act, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import {
  OrientationTour,
  requestHelpTourReplay,
  waitForTourTarget,
} from "../orientation-tour";
import {
  acknowledgeHelpTour,
  getUnseenHelpTour,
  replayHelpTour,
  type HelpTourRelease,
} from "../../services/help-api";

const joyrideState = vi.hoisted(() => ({
  props: null as Record<string, unknown> | null,
  navigate: vi.fn(),
}));

vi.mock("react-joyride", () => ({
  ACTIONS: { PREV: "prev" },
  EVENTS: { STEP_AFTER: "step:after", ERROR: "error" },
  STATUS: { FINISHED: "finished", SKIPPED: "skipped" },
  Joyride: (props: Record<string, unknown>) => {
    joyrideState.props = props;
    if (!props.run) return null;
    const Tooltip = props.tooltipComponent as ComponentType<Record<string, unknown>>;
    const steps = props.steps as Array<Record<string, unknown>>;
    const stepIndex = props.stepIndex as number;
    const step = steps[stepIndex];
    if (!step.skipBeacon) {
      return <button data-testid="help-tour-beacon" />;
    }
    const eventProps = {
      onClick: () => undefined,
      title: "action",
    };
    return createElement(Tooltip, {
      backProps: eventProps,
      closeProps: eventProps,
      continuous: true,
      index: stepIndex,
      isLastStep: stepIndex === steps.length - 1,
      primaryProps: eventProps,
      size: steps.length,
      skipProps: eventProps,
      step,
      tooltipProps: { "aria-modal": true, role: "dialog" },
    });
  },
}));

vi.mock("@tanstack/react-router", () => ({
  useNavigate: () => joyrideState.navigate,
}));

vi.mock("@/store/auth", () => ({
  useAuthStore: () => ({
    isAuthenticated: true,
    role: "tenant",
    tenantPlan: "starter",
    isMasterSupportContext: false,
  }),
}));

vi.mock("@/i18n", () => ({
  t: (key: string) => key,
}));

vi.mock("../config", () => ({
  HELP_TARGET_CONTRACT_VERSION: "2",
  isPrivateHelpEnabled: () => true,
}));

vi.mock("../safe-markdown", () => ({
  SafeMarkdown: ({ source }: { source: string }) => <p>{source}</p>,
}));

vi.mock("../../services/help-api", () => ({
  acknowledgeHelpTour: vi.fn(),
  getUnseenHelpTour: vi.fn(),
  replayHelpTour: vi.fn(),
}));

const release: HelpTourRelease = {
  release_id: "tenant-admin-starter-1",
  status: null,
  acknowledged_at: null,
  locale: "en",
  plan: "starter",
  frontend_target_contract_version: "2",
  steps: [
    {
      topic_id: "tenant-admin.dashboard",
      related_topics: [],
      title: "Dashboard",
      content: "Dashboard guidance",
      summary: "Dashboard summary",
      route: "/admin/dashboard",
      settings_category: null,
      target: "admin.dashboard",
      conditional: false,
      order: 1,
    },
  ],
};

describe("OrientationTour", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.stubEnv("VITE_PRIVATE_HELP_ENABLED", "true");
    joyrideState.props = null;
    joyrideState.navigate.mockReset();
    vi.mocked(getUnseenHelpTour).mockResolvedValue(release);
    vi.mocked(replayHelpTour).mockResolvedValue(release);
    vi.mocked(acknowledgeHelpTour).mockResolvedValue({
      release_id: release.release_id,
      status: "skipped",
      acknowledged_at: new Date().toISOString(),
    });
  });

  it("starts the unseen release with an anchored target and reduced-motion-safe scroll settings", async () => {
    render(
      <>
        <div data-help-id="admin.dashboard" />
        <OrientationTour />
      </>,
    );

    await waitFor(() => expect(getUnseenHelpTour).toHaveBeenCalled());
    await waitFor(() =>
      expect(screen.getByTestId("help-tour-popover")).toBeInTheDocument(),
    );
    expect(getUnseenHelpTour).toHaveBeenCalledOnce();
    expect(joyrideState.props?.options).toMatchObject({
      scrollDuration: 400,
      overlayClickAction: false,
      dismissKeyAction: false,
    });
    expect(joyrideState.props?.styles).toBeUndefined();
    expect(joyrideState.props?.steps).toEqual([
      expect.objectContaining({ target: '[data-help-id="admin.dashboard"]' }),
    ]);
  });

  it("requires confirmation before skipping and keeps replay available", async () => {
    const user = userEvent.setup();
    render(
      <>
        <div data-help-id="admin.dashboard" />
        <OrientationTour />
      </>,
    );

    await waitFor(() => expect(getUnseenHelpTour).toHaveBeenCalled());
    await waitFor(() =>
      expect(screen.getByTestId("help-tour-popover")).toBeInTheDocument(),
    );
    const skipButton = screen.getByRole("button", { name: "frontend.help.tour_skip" });
    skipButton.focus();
    await user.keyboard("{Enter}");

    expect(screen.getByRole("alertdialog")).toBeInTheDocument();
    expect(acknowledgeHelpTour).not.toHaveBeenCalled();

    await user.click(screen.getByRole("button", { name: "frontend.help.tour_keep_going" }));
    await waitFor(() =>
      expect(screen.getByTestId("help-tour-popover")).toBeInTheDocument(),
    );
    expect(acknowledgeHelpTour).not.toHaveBeenCalled();

    const skipAgain = screen.getByRole("button", { name: "frontend.help.tour_skip" });
    skipAgain.focus();
    await user.keyboard("{Enter}");

    await user.click(screen.getByRole("button", { name: "frontend.help.tour_confirm_skip" }));
    await waitFor(() =>
      expect(acknowledgeHelpTour).toHaveBeenCalledWith(
        release.release_id,
        "skipped",
      ),
    );

    act(() => requestHelpTourReplay());
    await waitFor(() => expect(replayHelpTour).toHaveBeenCalledWith());
  });

  it("replays the latest eligible tour after the unseen tour was acknowledged", async () => {
    vi.mocked(getUnseenHelpTour).mockRejectedValue(new Error("not found"));
    vi.mocked(replayHelpTour).mockResolvedValue(release);

    render(
      <>
        <div data-help-id="admin.dashboard" />
        <OrientationTour />
      </>,
    );

    await waitFor(() => expect(getUnseenHelpTour).toHaveBeenCalledOnce());
    expect(screen.queryByTestId("help-tour-popover")).not.toBeInTheDocument();

    act(() => requestHelpTourReplay());

    await waitFor(() => expect(replayHelpTour).toHaveBeenCalledWith());
    await waitFor(() =>
      expect(screen.getByTestId("help-tour-popover")).toBeInTheDocument(),
    );
  });

  it("replaces tour motion when the user prefers reduced motion", async () => {
    const originalMatchMedia = window.matchMedia;
    Object.defineProperty(window, "matchMedia", {
      configurable: true,
      value: vi.fn().mockReturnValue({
        matches: true,
        addEventListener: vi.fn(),
        removeEventListener: vi.fn(),
      }),
    });

    try {
      render(
        <>
          <div data-help-id="admin.dashboard" />
          <OrientationTour />
        </>,
      );

      await waitFor(() =>
        expect(screen.getByTestId("help-tour-popover")).toBeInTheDocument(),
      );
      expect(joyrideState.props?.options).toMatchObject({ scrollDuration: 0 });
      expect(joyrideState.props?.styles).toEqual({
        spotlight: { className: "transition-none" },
      });
      expect(screen.getByTestId("help-tour-popover")).toHaveAttribute(
        "data-reduced-motion",
        "true",
      );
    } finally {
      Object.defineProperty(window, "matchMedia", {
        configurable: true,
        value: originalMatchMedia,
      });
    }
  });

  it("opens the matching manual topic without performing a product action", async () => {
    const user = userEvent.setup();
    render(
      <>
        <div data-help-id="admin.dashboard" />
        <OrientationTour />
      </>,
    );

    await waitFor(() => expect(screen.getByTestId("help-tour-popover")).toBeInTheDocument());
    await user.click(screen.getByRole("button", { name: "frontend.help.tour_learn_more" }));

    expect(joyrideState.navigate).toHaveBeenCalledWith({
      to: "/admin/help",
      search: { topic: "tenant-admin.dashboard" },
    });
    expect(acknowledgeHelpTour).not.toHaveBeenCalled();
  });

  it("waits for a target and reports missing targets without guessing", async () => {
    const target = waitForTourTarget("admin.settings.profile", 100);
    window.setTimeout(() => {
      const element = document.createElement("div");
      element.dataset.helpId = "admin.settings.profile";
      document.body.appendChild(element);
    }, 10);

    await expect(target).resolves.toBe(true);
    await expect(waitForTourTarget("admin.missing", 1)).resolves.toBe(false);
  });
});
