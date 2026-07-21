import { Outlet, useLocation } from "@tanstack/react-router";
import { useAuthStore } from "@/store/auth";
import {
  AppSidebar,
  MobileSidebar,
} from "@/components/layout/app-sidebar";
import {
  createSidebarItems,
  getAdminNavigationItems,
} from "@/components/layout/role-navigation";
import { SupportBanner } from "@/features/admin/components/support-banner";

export function AdminLayout() {
  const { username, logout, role, tenantPlan, isMasterSupportContext } = useAuthStore();
  const location = useLocation();

  const isStarterTenantAdmin = role === "tenant" && tenantPlan === "starter";
  const showProNav = !isStarterTenantAdmin || isMasterSupportContext;
  const sidebarItems = createSidebarItems(
    getAdminNavigationItems(showProNav),
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
        {isMasterSupportContext && tenantPlan === "starter" && <SupportBanner />}
        <Outlet />
      </main>
    </div>
  );
}
