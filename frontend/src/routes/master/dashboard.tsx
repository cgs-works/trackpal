import { createFileRoute } from "@tanstack/react-router";
import { DashboardPage } from "@/features/master/components/dashboard-page";

export const Route = createFileRoute("/master/dashboard")({
  component: DashboardPage,
});
