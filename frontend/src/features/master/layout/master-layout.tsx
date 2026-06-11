import { useState } from "react";
import { Outlet, Navigate, useNavigate } from "@tanstack/react-router";
import { LayoutDashboard, Settings } from "lucide-react";
import { useAuthStore } from "@/store/auth";
import {
  AppSidebar,
  MobileSidebar,
  type SidebarItem,
} from "@/components/layout/app-sidebar";
import { CodeServicesDialog } from "../components/code-services-dialog";

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
      active: true,
      onSelect: () => navigate({ to: "/master/dashboard" }),
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

        <div className="flex-1 flex flex-col min-h-screen overflow-auto">
          <Outlet />
        </div>
      </div>

      <CodeServicesDialog
        open={codeServicesOpen}
        onOpenChange={setCodeServicesOpen}
      />
    </div>
  );
}
