import {
  isSettingsCategoryId,
  type SettingsCategoryId,
} from "@/features/admin/settings-categories";
import type { HelpSafeNavigation } from "./services/help-api";

export type SafeHelpDestination =
  | { to: "/admin/dashboard" }
  | { to: "/admin/clients" }
  | { to: "/admin/catalog" }
  | { to: "/admin/subscriptions" }
  | { to: "/admin/settings"; search?: { category?: SettingsCategoryId } }
  | { to: "/admin/help"; search?: { topic?: string } }
  | { to: "/client/dashboard" }
  | { to: "/client/profile" }
  | { to: "/client/help" };

export function resolveSafeHelpNavigation(
  navigation: HelpSafeNavigation,
  audience: "tenant" | "client" = "tenant",
): SafeHelpDestination | null {
  const isClientRoute = navigation.route.startsWith("/client/");
  if ((audience === "client" && !isClientRoute) || (audience === "tenant" && isClientRoute)) {
    return null;
  }

  if (navigation.route === "/admin/dashboard" && navigation.settings_category === null) {
    return { to: "/admin/dashboard" };
  }

  if (navigation.route === "/client/dashboard" && navigation.settings_category === null) {
    return { to: "/client/dashboard" };
  }

  if (navigation.route === "/client/profile" && navigation.settings_category === null) {
    return { to: "/client/profile" };
  }

  if (navigation.route === "/client/help" && navigation.settings_category === null) {
    return { to: "/client/help" };
  }

  if (navigation.settings_category === null) {
    if (navigation.route === "/admin/clients") {
      return { to: "/admin/clients" };
    }
    if (navigation.route === "/admin/catalog") {
      return { to: "/admin/catalog" };
    }
    if (navigation.route === "/admin/subscriptions") {
      return { to: "/admin/subscriptions" };
    }
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

  if (navigation.route === "/admin/help" && navigation.settings_category === null) {
    return { to: "/admin/help" };
  }

  return null;
}
