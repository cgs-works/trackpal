import { createFileRoute } from "@tanstack/react-router";
import { DashboardPage } from "@/features/client/components/dashboard-page";

export const Route = createFileRoute("/client/dashboard")({
  component: DashboardPage,
});
