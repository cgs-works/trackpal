import { createFileRoute } from "@tanstack/react-router";
import { SettingsPage } from "@/features/admin/components/settings-page";
import {
  isSettingsCategoryId,
  type SettingsCategoryId,
} from "@/features/admin/settings-categories";

function validateSearch(search: Record<string, unknown>): {
  category?: SettingsCategoryId;
} {
  const category = search.category;
  return {
    category:
      typeof category === "string" && isSettingsCategoryId(category)
        ? category
        : undefined,
  };
}

function SettingsRoute() {
  const { category } = Route.useSearch();
  return <SettingsPage initialSection={category} />;
}

export const Route = createFileRoute("/admin/settings")({
  validateSearch,
  component: SettingsRoute,
});
