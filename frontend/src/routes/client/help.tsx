import { createFileRoute } from "@tanstack/react-router";
import { HelpCenterPage } from "@/features/help/components/help-center-page";

export const Route = createFileRoute("/client/help")({
  component: () => <HelpCenterPage audience="client" />,
});
