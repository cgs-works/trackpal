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
import { ContextualHelpSheet } from "@/features/help/components/contextual-help-sheet";
import { isPrivateHelpEnabled } from "@/features/help/config";

export function ClientLayout() {
  const { username, logout, user, role, activeTenantId } = useAuthStore();
  const location = useLocation();
  const showContextualHelp =
    role === "client" &&
    isPrivateHelpEnabled() &&
    (location.pathname === "/client/dashboard" ||
      location.pathname === "/client/profile");
  const sidebarItems = createSidebarItems(
    getClientNavigationItems(isPrivateHelpEnabled()),
    location.pathname,
  );
  const helpSessionKey = `${user?.id ?? "anonymous"}:${role}:${activeTenantId ?? "none"}`;

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
        {showContextualHelp && (
          <div className="flex justify-end border-b px-4 py-2 sm:px-6">
            <ContextualHelpSheet audience="client" />
          </div>
        )}
        <Outlet />
      </main>
    </div>
  );
}
