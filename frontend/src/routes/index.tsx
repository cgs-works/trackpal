import { createFileRoute, useNavigate } from "@tanstack/react-router";
import { useEffect } from "react";
import { useAuthStore } from "@/store/auth";

export const Route = createFileRoute("/")({
  component: IndexComponent,
});

function IndexComponent() {
  const navigate = useNavigate();
  const { isAuthenticated, role, authOutcome } = useAuthStore();

  useEffect(() => {
    if (authOutcome === "demo_ended" || authOutcome === "demo_credentials_replaced") {
      navigate({ to: "/demo-ended", replace: true });
    } else if (isAuthenticated) {
      if (role === "master") {
        navigate({ to: "/master/dashboard", replace: true });
      } else if (role === "tenant") {
        navigate({ to: "/admin/dashboard", replace: true });
      } else if (role === "client") {
        navigate({ to: "/client/dashboard", replace: true });
      }
    } else {
      navigate({ to: "/login", replace: true });
    }
  }, [isAuthenticated, role, authOutcome, navigate]);

  return (
    <div className="flex-1 flex items-center justify-center">
      <p className="text-muted-foreground">Redirecting...</p>
    </div>
  );
}
