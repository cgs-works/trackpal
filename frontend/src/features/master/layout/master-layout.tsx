import { useState } from "react";
import { Outlet, Navigate, useNavigate } from "@tanstack/react-router";
import { LayoutDashboard, ServerCog, Settings } from "lucide-react";
import { useAuthStore } from "@/store/auth";
import {
  AppSidebar,
  MobileSidebar,
  type SidebarItem,
} from "@/components/layout/app-sidebar";
import { CodeServicesDialog } from "../components/code-services-dialog";
import { LegalFooter } from "@/components/layout/legal-footer";
import { t } from "@/i18n";

export function MasterLayout() {
  const navigate = useNavigate();
  const { isAuthenticated, role, username, logout } = useAuthStore();
  const [codeServicesOpen, setCodeServicesOpen] = useState(false);

  if (!isAuthenticated || role !== "master") {
    return <Navigate to="/login" replace />;
  }

  async function handleLogout() {
    await logout();
    await navigate({ to: "/login" });
  }

  const sidebarItems: SidebarItem[] = [
    {
      label: "Dashboard",
      icon: <LayoutDashboard className="size-4 shrink-0" />,
      to: "/master/dashboard",
    },
    {
      label: t("frontend.master.executors.navigation"),
      icon: <ServerCog className="size-4 shrink-0" />,
      to: "/master/executors",
    },
    {
      label: "Code Services",
      icon: <Settings className="size-4 shrink-0" />,
      onSelect: () => setCodeServicesOpen(true),
    },
  ];

  return (
    <div className="min-h-screen flex flex-col bg-background">
      <MobileSidebar
        username={username || "Master"}
        items={sidebarItems}
        onLogout={handleLogout}
      />

      <div className="flex flex-1 overflow-hidden">
        <AppSidebar
          username={username || "Master"}
          items={sidebarItems}
          onLogout={handleLogout}
        />

        <div className="flex-1 flex min-h-screen flex-col overflow-auto">
          <Outlet />
          <div className="px-4 pb-6 pt-8 sm:px-6">
            <LegalFooter />
          </div>
        </div>
      </div>

      <CodeServicesDialog
        open={codeServicesOpen}
        onOpenChange={setCodeServicesOpen}
      />
    </div>
  );
}
