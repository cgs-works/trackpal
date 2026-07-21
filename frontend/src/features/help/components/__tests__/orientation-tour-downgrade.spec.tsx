import { render, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { OrientationTour } from "../orientation-tour";
import { getUnseenHelpTour } from "../../services/help-api";

vi.mock("react-joyride", () => ({
  ACTIONS: { PREV: "prev" },
  EVENTS: { STEP_AFTER: "step:after", ERROR: "error" },
  STATUS: { FINISHED: "finished", SKIPPED: "skipped" },
  Joyride: () => null,
}));

vi.mock("@tanstack/react-router", () => ({
  useNavigate: () => vi.fn(),
}));

vi.mock("@/store/auth", () => ({
  useAuthStore: () => ({
    isAuthenticated: true,
    role: "tenant",
    tenantPlan: "starter",
    planDowngraded: true,
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
  SafeMarkdown: () => null,
}));

vi.mock("../../services/help-api", () => ({
  acknowledgeHelpTour: vi.fn(),
  getUnseenHelpTour: vi.fn(),
  replayHelpTour: vi.fn(),
}));

describe("OrientationTour after a downgrade", () => {
  it("does not request or start a downgrade tour", async () => {
    render(<OrientationTour />);

    await waitFor(() => expect(getUnseenHelpTour).not.toHaveBeenCalled());
  });
});
