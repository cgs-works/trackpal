export const SETTINGS_CATEGORY_IDS = [
  "reminders",
  "public-api",
  "code-services",
  "mailbox",
  "access-control",
  "my-account",
  "whatsapp-link",
] as const;

export type SettingsCategoryId = (typeof SETTINGS_CATEGORY_IDS)[number];

export function isSettingsCategoryId(value: string): value is SettingsCategoryId {
  return (SETTINGS_CATEGORY_IDS as readonly string[]).includes(value);
}
