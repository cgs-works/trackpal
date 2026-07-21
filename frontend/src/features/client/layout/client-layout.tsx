import { Outlet, useLocation } from "@tanstack/react-router";
import { useAuthStore } from "@/store/auth";
import {
  AppSidebar,
  MobileSidebar,
} from "@/components/layout/app-sidebar";
import {
  createSidebarItems,
  getClientNavigationItems,
} from "@/components/layout/role-navigation";

export function ClientLayout() {
  const { username, logout } = useAuthStore();
  const location = useLocation();
  const sidebarItems = createSidebarItems(
    getClientNavigationItems(),
    location.pathname,
  );

  function handleLogout() {
    void logout();
  }

  return (
    <div className="flex h-screen flex-col bg-background/80 md:flex-row">
      <MobileSidebar
        username={username}
        items={sidebarItems}
        onLogout={handleLogout}
      />

      <AppSidebar
        username={username}
        items={sidebarItems}
        onLogout={handleLogout}
      />

      <main className="flex-1 overflow-y-auto">
        <Outlet />
      </main>
    </div>
  );
}
