import { useState } from "react";
import { Outlet, Link, useLocation } from "@tanstack/react-router";
import { useAuthStore } from "@/store/auth";
import { Button } from "@/components/ui/button";
import {
  LayoutDashboard,
  User,
  LogOut,
  PanelLeftClose,
  PanelLeft,
} from "lucide-react";
import { t } from "@/i18n";

export function ClientLayout() {
  const NAV_ITEMS = [
    { to: "/client/dashboard", label: t("frontend.dashboard.client.title"), icon: LayoutDashboard },
    { to: "/client/profile", label: t("frontend.dashboard.client.profile"), icon: User },
  ];
  const { username, logout } = useAuthStore();
  const location = useLocation();
  const [collapsed, setCollapsed] = useState(false);

  return (
    <div className="flex h-screen bg-background">
      {/* ── Sidebar ──────────────────────────────────────────── */}
      <aside
        className={`hidden md:flex flex-col border-r border-border transition-all duration-200 ${
          collapsed ? "w-[60px]" : "w-[220px]"
        }`}
      >
        {/* Brand */}
        <div className="flex items-center gap-2 h-14 px-4 border-b border-border">
          {!collapsed && (
            <span className="font-bold text-lg tracking-tight">TrackPal</span>
          )}
          <Button
            variant="ghost"
            size="icon"
            className="ml-auto h-8 w-8 shrink-0"
            onClick={() => setCollapsed(!collapsed)}
          >
            {collapsed ? (
              <PanelLeft className="size-4" />
            ) : (
              <PanelLeftClose className="size-4" />
            )}
          </Button>
        </div>

        {/* Navigation */}
        <nav className="flex-1 p-2 space-y-1">
          {NAV_ITEMS.map((item) => {
            const isActive = location.pathname === item.to;
            return (
              <Link
                key={item.to}
                to={item.to}
                className={`flex items-center gap-3 px-3 py-2 rounded-lg text-sm font-medium transition-colors ${
                  isActive
                    ? "bg-primary text-primary-foreground"
                    : "text-muted-foreground hover:bg-accent hover:text-accent-foreground"
                }`}
              >
                <item.icon className="size-4 shrink-0" />
                {!collapsed && <span>{item.label}</span>}
              </Link>
            );
          })}
        </nav>

        {/* User */}
        <div className="p-2 border-t border-border">
          {!collapsed && (
            <div className="px-3 py-2 text-sm text-muted-foreground truncate">
              {username}
            </div>
          )}
          <Button
            variant="ghost"
            className="w-full justify-start gap-3 px-3"
            onClick={() => logout()}
          >
            <LogOut className="size-4 shrink-0" />
            {!collapsed && <span>Logout</span>}
          </Button>
        </div>
      </aside>

      {/* ── Mobile header ────────────────────────────────────── */}
      <div className="md:hidden fixed top-0 left-0 right-0 z-40 flex items-center gap-3 h-14 px-4 border-b border-border bg-background">
        <span className="font-bold text-lg tracking-tight">TrackPal</span>
        <div className="ml-auto flex items-center gap-2">
          <span className="text-sm text-muted-foreground">{username}</span>
          <Button variant="ghost" size="icon" onClick={() => logout()}>
            <LogOut className="size-4" />
          </Button>
        </div>
      </div>

      {/* ── Main content ─────────────────────────────────────── */}
      <main className="flex-1 overflow-y-auto md:pt-0 pt-14">
        <Outlet />
      </main>
    </div>
  );
}
