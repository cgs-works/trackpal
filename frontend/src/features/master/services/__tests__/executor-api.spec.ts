import { describe, expect, it, vi } from "vitest";

vi.mock("@/i18n", () => ({
  t: (key: string) => key,
}));

import { mapExecutorError } from "../executor-api";

describe("mapExecutorError", () => {
  it.each([
    ["insecure_http_confirmation_required", "error_insecure_http_confirmation_required"],
    ["executor_requires_verification", "error_requires_verification"],
    ["step_up_rate_limited", "error_step_up_rate_limited"],
  ])("maps %s to its translated key", (code, errorKey) => {
    const error = { response: { data: { detail: code } } };

    expect(mapExecutorError(error, "frontend.master.executors.error_load")).toBe(
      `frontend.master.executors.${errorKey}`,
    );
  });
});
