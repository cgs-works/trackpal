import { createFileRoute, Outlet, Navigate, useNavigate } from "@tanstack/react-router";
import { useAuthStore } from "@/store/auth";
import { Button } from "@/components/ui/button";

export const Route = createFileRoute("/master")({
  component: MasterLayout,
});

function MasterLayout() {
  const navigate = useNavigate();
  const { username, logout, isAuthenticated, role } = useAuthStore();

  if (!isAuthenticated || role !== "master") {
    return <Navigate to="/login" replace />;
  }

  async function handleLogout() {
    await logout();
    await navigate({ to: "/login" });
  }

  return (
    <div className="min-h-screen flex flex-col bg-muted/30">
      <header className="bg-card border-b px-6 py-4 flex items-center justify-between shadow-sm">
        <div className="flex items-center gap-6">
          <span className="text-xl font-bold tracking-tight text-primary">
            TrackPal
          </span>
          <span className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
            Master Dashboard
          </span>
        </div>
        <div className="flex items-center gap-4">
          <span className="text-sm font-medium text-muted-foreground">
            {username || "Master"}
          </span>
          <Button variant="outline" size="sm" onClick={handleLogout}>
            Logout
          </Button>
        </div>
      </header>

      <main className="flex-1">
        <Outlet />
      </main>
    </div>
  );
}
