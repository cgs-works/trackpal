/**
 * Release gate for Gmail OAuth connect UI.
 * Only the exact string "true" enables the feature.
 */
export function isGmailOAuthConnectEnabled(): boolean {
  return import.meta.env.VITE_GMAIL_OAUTH_CONNECT_ENABLED === "true";
}
