import { createFileRoute } from "@tanstack/react-router";
import { PasswordPage } from "@/features/client/components/password-page";

export const Route = createFileRoute("/client/password")({
  component: PasswordPage,
});
