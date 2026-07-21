import {
  isSettingsCategoryId,
  type SettingsCategoryId,
} from "@/features/admin/settings-categories";
import type { HelpSafeNavigation } from "./services/help-api";

export type SafeHelpDestination =
  | { to: "/admin/dashboard" }
  | { to: "/admin/settings"; search?: { category?: SettingsCategoryId } };

export function resolveSafeHelpNavigation(
  navigation: HelpSafeNavigation,
): SafeHelpDestination | null {
  if (navigation.route === "/admin/dashboard" && navigation.settings_category === null) {
    return { to: "/admin/dashboard" };
  }

  if (
    navigation.route === "/admin/settings" &&
    (navigation.settings_category === null ||
      isSettingsCategoryId(navigation.settings_category))
  ) {
    return navigation.settings_category === null
      ? { to: "/admin/settings" }
      : {
          to: "/admin/settings",
          search: { category: navigation.settings_category },
        };
  }

  return null;
}
