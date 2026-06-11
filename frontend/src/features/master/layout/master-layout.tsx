import { Outlet, Navigate } from "@tanstack/react-router";
import { useAuthStore } from "@/store/auth";
import { AppSidebar, MobileSidebar } from "@/components/layout/app-sidebar";

export function MasterLayout() {
  const { isAuthenticated, role } = useAuthStore();

  if (!isAuthenticated || role !== "master") {
    return <Navigate to="/login" replace />;
  }

  return (
    <div className="min-h-screen flex flex-col bg-background">
      <MobileSidebar />
      <div className="flex flex-1 overflow-hidden">
        <AppSidebar />
        <div className="flex-1 flex flex-col min-h-screen overflow-auto">
          <Outlet />
        </div>
      </div>
    </div>
  );
}
