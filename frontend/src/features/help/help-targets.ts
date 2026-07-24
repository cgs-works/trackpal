export const HELP_TARGETS = {
  dashboard: "admin.dashboard",
  clients: "admin.clients",
  catalog: "admin.catalog",
  subscriptions: "admin.subscriptions",
  settings: "admin.settings",
  language: "admin.settings.language",
  reminders: "admin.settings.reminders",
  timezone: "admin.settings.timezone",
  publicApi: "admin.settings.public-api",
  whatsapp: "admin.settings.whatsapp",
  codeServices: "admin.settings.code-services",
  mailbox: "admin.settings.mailbox",
  accessControl: "admin.settings.access-control",
  profile: "admin.settings.profile",
  myAccount: "admin.settings.my-account",
  help: "admin.help",
  clientDashboard: "client.dashboard",
  clientProfile: "client.profile",
  clientSubscriptions: "client.subscriptions",
  clientPassword: "client.password",
} as const;

export type HelpTargetId = (typeof HELP_TARGETS)[keyof typeof HELP_TARGETS];

export function findActiveHelpTarget(root: ParentNode = document): string | null {
  const targets = Array.from(root.querySelectorAll<HTMLElement>("[data-help-id]"))
    .filter((element) => !element.hidden && element.getAttribute("aria-hidden") !== "true")
    .map((element) => element.dataset.helpId)
    .filter((target): target is string => Boolean(target));

  return targets.sort((left, right) => right.length - left.length)[0] ?? null;
}
