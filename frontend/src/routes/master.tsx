import { createFileRoute, Outlet, Navigate } from "@tanstack/react-router";
import { useAuthStore } from "@/store/auth";
import { AppSidebar, MobileSidebar } from "@/components/layout/app-sidebar";

export const Route = createFileRoute("/master")({
  component: MasterLayout,
});

function MasterLayout() {
  const { isAuthenticated, role } = useAuthStore();

  if (!isAuthenticated || role !== "master") {
    return <Navigate to="/login" replace />;
  }

  return (
    <div className="min-h-screen flex flex-col bg-background">
      {/* Mobile header */}
      <MobileSidebar />

      <div className="flex flex-1 overflow-hidden">
        {/* Desktop sidebar */}
        <AppSidebar />

        {/* Main content */}
        <div className="flex-1 flex flex-col min-h-screen overflow-auto">
          <Outlet />
        </div>
      </div>
    </div>
  );
}
