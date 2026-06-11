import { createFileRoute } from "@tanstack/react-router";
import { DashboardPage } from "@/features/admin/components/dashboard-page";

export const Route = createFileRoute("/admin/dashboard")({
  component: DashboardPage,
});
