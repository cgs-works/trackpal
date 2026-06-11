import { createFileRoute, Navigate } from "@tanstack/react-router";
import { useAuthStore } from "@/store/auth";

export const Route = createFileRoute("/client/dashboard")({
  component: ClientDashboardPlaceholder,
});

function ClientDashboardPlaceholder() {
  const { isAuthenticated, role } = useAuthStore();

  if (!isAuthenticated || role !== "client") {
    return <Navigate to="/login" replace />;
  }

  return (
    <div className="min-h-screen flex flex-col bg-muted/30">
      <div className="flex-1 flex items-center justify-center">
        <p className="text-muted-foreground">Client dashboard — coming soon</p>
      </div>
    </div>
  );
}
