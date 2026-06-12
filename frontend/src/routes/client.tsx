import { createFileRoute } from "@tanstack/react-router";
import { ClientLayout } from "@/features/client/layout/client-layout";

export const Route = createFileRoute("/client")({
  component: ClientLayout,
});
