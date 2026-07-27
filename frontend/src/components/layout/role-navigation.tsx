import type { LucideIcon } from "lucide-react";
import {
  CreditCard,
  HelpCircle,
  LayoutDashboard,
  MessageCircle,
  Package,
  Settings,
  User,
  Users,
} from "lucide-react";
import { t } from "@/i18n";
import type { SidebarItem } from "./app-sidebar";

export type AdminNavigationPath =
  | "/admin/dashboard"
  | "/admin/clients"
  | "/admin/catalog"
  | "/admin/subscriptions"
  | "/admin/settings"
  | "/admin/help"
  | "/admin/demo/simulator";

export type ClientNavigationPath =
  | "/client/dashboard"
  | "/client/profile"
  | "/client/help";

type NavigationItem<Path extends string> = {
  to: Path;
  label: string;
  icon: LucideIcon;
  proOnly?: boolean;
  activeMatch: "exact" | "prefix";
};

export type AdminNavigationItem = NavigationItem<AdminNavigationPath>;
export type ClientNavigationItem = NavigationItem<ClientNavigationPath>;

export function getAdminNavigationItems(
  showProNav: boolean,
  showHelp = false,
  showSimulator = false,
): AdminNavigationItem[] {
  const items: AdminNavigationItem[] = [
    {
      to: "/admin/dashboard",
      label: t("frontend.dashboard.tenant.title"),
      icon: LayoutDashboard,
      activeMatch: "prefix",
    },
    {
      to: "/admin/clients",
      label: t("frontend.clients.section_title"),
      icon: Users,
      proOnly: true,
      activeMatch: "prefix",
    },
    {
      to: "/admin/catalog",
      label: t("frontend.catalog.section_title"),
      icon: Package,
      proOnly: true,
      activeMatch: "prefix",
    },
    {
      to: "/admin/subscriptions",
      label: t("frontend.subscriptions.title"),
      icon: CreditCard,
      proOnly: true,
      activeMatch: "prefix",
    },
    {
      to: "/admin/settings",
      label: t("frontend.settings.section_title"),
      icon: Settings,
      activeMatch: "prefix",
    },
  ];

  if (showSimulator) {
    items.push({
      to: "/admin/demo/simulator",
      label: t("frontend.demo_simulator.title"),
      icon: MessageCircle,
      activeMatch: "prefix",
    });
  }

  if (showHelp) {
    items.push({
      to: "/admin/help",
      label: t("frontend.help.title"),
      icon: HelpCircle,
      activeMatch: "prefix",
    });
  }

  return items.filter((item) => showProNav || !item.proOnly);
}

export function getClientNavigationItems(showHelp = false): ClientNavigationItem[] {
  const items: ClientNavigationItem[] = [
    {
      to: "/client/dashboard",
      label: t("frontend.dashboard.client.title"),
      icon: LayoutDashboard,
      activeMatch: "exact",
    },
    {
      to: "/client/profile",
      label: t("frontend.dashboard.client.profile"),
      icon: User,
      activeMatch: "exact",
    },
  ];

  if (showHelp) {
    items.push({
      to: "/client/help",
      label: t("frontend.help.title"),
      icon: HelpCircle,
      activeMatch: "prefix",
    });
  }

  return items;
}

export function createSidebarItems<Path extends string>(
  items: readonly NavigationItem<Path>[],
  pathname: string,
): SidebarItem[] {
  return items.map((item) => {
    const Icon = item.icon;
    const active =
      item.activeMatch === "prefix"
        ? pathname.startsWith(item.to)
        : pathname === item.to;

    return {
      label: item.label,
      icon: <Icon className="size-4 shrink-0" />,
      active,
      to: item.to,
    };
  });
}
