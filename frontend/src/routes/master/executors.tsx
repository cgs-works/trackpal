import { createFileRoute } from "@tanstack/react-router";
import { LookupExecutorsPage } from "@/features/master/components/lookup-executors-page";

export const Route = createFileRoute("/master/executors")({
  component: LookupExecutorsPage,
});
