export const HELP_TARGET_CONTRACT_VERSION = "2";

export function isPrivateHelpEnabled(): boolean {
  return import.meta.env.VITE_PRIVATE_HELP_ENABLED === "true";
}
