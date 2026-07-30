import type { HelpTargetId } from "./help-targets";

export const CONTEXTUAL_HELP_REQUEST_EVENT = "trackpal:contextual-help-request";

export function requestContextualHelp(target: HelpTargetId): void {
  window.dispatchEvent(
    new CustomEvent<HelpTargetId>(CONTEXTUAL_HELP_REQUEST_EVENT, { detail: target }),
  );
}
