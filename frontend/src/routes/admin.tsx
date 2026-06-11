import { createFileRoute } from "@tanstack/react-router";
import { AdminLayout } from "@/features/admin/layout/admin-layout";

export const Route = createFileRoute("/admin")({
  component: AdminLayout,
});
