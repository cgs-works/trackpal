export function isPrivateHelpEnabled(): boolean {
  return import.meta.env.VITE_PRIVATE_HELP_ENABLED === "true";
}
