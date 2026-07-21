import { createFileRoute } from "@tanstack/react-router";
import { HelpCenterPage } from "@/features/help/components/help-center-page";

function validateSearch(search: Record<string, unknown>): { topic?: string } {
  return {
    topic: typeof search.topic === "string" ? search.topic : undefined,
  };
}

function AdminHelpRoute() {
  const { topic } = Route.useSearch();
  return <HelpCenterPage audience="tenant" initialTopicId={topic} />;
}

export const Route = createFileRoute("/admin/help")({
  validateSearch,
  component: AdminHelpRoute,
});
