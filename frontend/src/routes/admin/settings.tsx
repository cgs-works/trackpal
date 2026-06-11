import { createFileRoute } from "@tanstack/react-router";
import { SettingsPage } from "@/features/admin/components/settings-page";

export const Route = createFileRoute("/admin/settings")({
  component: SettingsPage,
});
