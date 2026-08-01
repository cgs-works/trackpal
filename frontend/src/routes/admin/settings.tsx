import { createFileRoute } from "@tanstack/react-router";
import { SettingsPage } from "@/features/admin/components/settings-page";
import {
  isSettingsCategoryId,
  type SettingsCategoryId,
} from "@/features/admin/settings-categories";

const VALID_TABS = ["regional"] as const;

type TabValue = (typeof VALID_TABS)[number];

function validateSearch(search: Record<string, unknown>): {
  category?: SettingsCategoryId;
  tab?: TabValue;
} {
  const category = search.category;
  const tab = search.tab;

  return {
    category:
      typeof category === "string" && isSettingsCategoryId(category)
        ? category
        : undefined,
    tab:
      typeof tab === "string" && (VALID_TABS as readonly string[]).includes(tab)
        ? (tab as TabValue)
        : undefined,
  };
}

function SettingsRoute() {
  const { category, tab } = Route.useSearch();
  return <SettingsPage initialSection={category} initialTab={tab} />;
}

export const Route = createFileRoute("/admin/settings")({
  validateSearch,
  component: SettingsRoute,
});
