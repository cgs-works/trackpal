import { createFileRoute } from "@tanstack/react-router";
import { ProfilePage } from "@/features/client/components/profile-page";

export const Route = createFileRoute("/client/profile")({
  component: ProfilePage,
});
