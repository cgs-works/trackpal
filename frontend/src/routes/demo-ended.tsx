import { createFileRoute } from "@tanstack/react-router";
import { DemoEndedPage } from "@/features/demo/components/demo-ended-page";

export const Route = createFileRoute("/demo-ended")({
  component: DemoEndedPage,
});
