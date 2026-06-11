import { createFileRoute } from "@tanstack/react-router";
import { MasterLayout } from "@/features/master/layout/master-layout";

export const Route = createFileRoute("/master")({
  component: MasterLayout,
});
