import { createFileRoute } from "@tanstack/react-router";
import { DemoWhatsappSimulator } from "@/features/demo/components/demo-whatsapp-simulator";

export const Route = createFileRoute("/admin/demo/simulator")({
  component: DemoWhatsappSimulator,
});
