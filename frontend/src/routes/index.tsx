import { createFileRoute, useNavigate } from "@tanstack/react-router";
import { useEffect } from "react";
import { useAuthStore } from "@/store/auth";

export const Route = createFileRoute("/")({
  component: IndexComponent,
});

function IndexComponent() {
  const navigate = useNavigate();
  const { isAuthenticated, role } = useAuthStore();

  useEffect(() => {
    if (isAuthenticated) {
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
  }, [isAuthenticated, role, navigate]);

  return (
    <div className="flex-1 flex items-center justify-center">
      <p className="text-muted-foreground">Redirecting...</p>
    </div>
  );
}
