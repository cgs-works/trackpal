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
import { DowngradeBanner } from "@/features/admin/components/downgrade-banner";
import { SupportBanner } from "@/features/admin/components/support-banner";
import { ContextualHelpSheet } from "@/features/help/components/contextual-help-sheet";
import { isPrivateHelpEnabled } from "@/features/help/config";
import { OrientationTour } from "@/features/help/components/orientation-tour";

export function AdminLayout() {
  const {
    username,
    logout,
    user,
    role,
    activeTenantId,
    tenantPlan,
    planDowngraded,
    isMasterSupportContext,
  } = useAuthStore();
  const location = useLocation();

  const isStarterTenantAdmin = role === "tenant" && tenantPlan === "starter";
  const showProNav = !isStarterTenantAdmin || isMasterSupportContext;
  const showContextualHelp =
    role === "tenant" &&
    isPrivateHelpEnabled() &&
    (location.pathname === "/admin/dashboard" ||
      location.pathname === "/admin/clients" ||
      location.pathname === "/admin/catalog" ||
      location.pathname === "/admin/subscriptions" ||
      location.pathname === "/admin/settings");
  const sidebarItems = createSidebarItems(
    getAdminNavigationItems(
      showProNav,
      role === "tenant" && isPrivateHelpEnabled(),
    ),
    location.pathname,
  );
  const helpSessionKey = `${user?.id ?? "anonymous"}:${role}:${activeTenantId ?? "none"}:${tenantPlan ?? "none"}:${planDowngraded}`;

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

      <main key={helpSessionKey} className="flex-1 overflow-y-auto">
        {isMasterSupportContext && tenantPlan === "starter" && <SupportBanner />}
        {role === "tenant" && planDowngraded && tenantPlan === "starter" && (
          <DowngradeBanner />
        )}
        {showContextualHelp && (
          <div className="flex justify-end border-b px-4 py-2 sm:px-6">
            <ContextualHelpSheet />
          </div>
        )}
        <Outlet />
        <OrientationTour />
      </main>
    </div>
  );
}
