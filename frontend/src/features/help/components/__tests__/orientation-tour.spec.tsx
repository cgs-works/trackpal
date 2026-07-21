import { createElement, type ComponentType } from "react";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { OrientationTour, requestHelpTourReplay } from "../orientation-tour";
import {
  acknowledgeHelpTour,
  getUnseenHelpTour,
  replayHelpTour,
  type HelpTourRelease,
} from "../../services/help-api";

const joyrideState = vi.hoisted(() => ({
  props: null as Record<string, unknown> | null,
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
      step: steps[stepIndex],
      tooltipProps: { "aria-modal": true, role: "dialog" },
    });
  },
}));

vi.mock("@tanstack/react-router", () => ({
  useNavigate: () => vi.fn(),
}));

vi.mock("@/store/auth", () => ({
  useAuthStore: () => ({
    isAuthenticated: true,
    role: "tenant",
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
  release_id: "tenant-admin-tracer-1",
  status: null,
  acknowledged_at: null,
  locale: "en",
  plan: "starter",
  frontend_target_contract_version: "2",
  steps: [
    {
      topic_id: "tenant-admin.dashboard",
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
    vi.mocked(getUnseenHelpTour).mockResolvedValue(release);
    vi.mocked(replayHelpTour).mockResolvedValue(release);
    vi.mocked(acknowledgeHelpTour).mockResolvedValue({
      release_id: release.release_id,
      status: "skipped",
      acknowledged_at: new Date().toISOString(),
    });
  });

  it("starts the unseen release with an anchored target and reduced-motion-safe scroll settings", async () => {
    render(<OrientationTour />);

    await waitFor(() => expect(getUnseenHelpTour).toHaveBeenCalled());
    expect(screen.getByTestId("help-tour-popover")).toBeInTheDocument();
    expect(getUnseenHelpTour).toHaveBeenCalledOnce();
    expect(joyrideState.props?.options).toMatchObject({
      scrollDuration: 400,
      overlayClickAction: false,
      dismissKeyAction: false,
    });
    expect(joyrideState.props?.steps).toEqual([
      expect.objectContaining({ target: '[data-help-id="admin.dashboard"]' }),
    ]);
  });

  it("requires confirmation before skipping and keeps replay available", async () => {
    const user = userEvent.setup();
    render(<OrientationTour />);

    await waitFor(() => expect(getUnseenHelpTour).toHaveBeenCalled());
    expect(screen.getByTestId("help-tour-popover")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "frontend.help.tour_skip" }));

    expect(screen.getByRole("alertdialog")).toBeInTheDocument();
    expect(acknowledgeHelpTour).not.toHaveBeenCalled();

    await user.click(screen.getByRole("button", { name: "frontend.help.tour_confirm_skip" }));
    await waitFor(() =>
      expect(acknowledgeHelpTour).toHaveBeenCalledWith(
        release.release_id,
        "skipped",
      ),
    );

    requestHelpTourReplay();
    await waitFor(() => expect(replayHelpTour).toHaveBeenCalledWith(release.release_id));
  });
});
