import { createFileRoute } from "@tanstack/react-router";
import { ClientsPage } from "@/features/admin/components/clients-page";

export const Route = createFileRoute("/admin/clients")({
  component: ClientsPage,
});
