import { createFileRoute, Navigate } from "@tanstack/react-router";
import { useAuthStore } from "@/store/auth";

export const Route = createFileRoute("/admin/dashboard")({
  component: AdminDashboardPlaceholder,
});

function AdminDashboardPlaceholder() {
  const { isAuthenticated, role } = useAuthStore();

  if (!isAuthenticated || role !== "tenant") {
    return <Navigate to="/login" replace />;
  }

  return (
    <div className="min-h-screen flex flex-col bg-muted/30">
      <div className="flex-1 flex items-center justify-center">
        <p className="text-muted-foreground">Tenant dashboard — coming soon</p>
      </div>
    </div>
  );
}
