import { useState } from "react";
import { Outlet, Link, useLocation } from "@tanstack/react-router";
import { useAuthStore } from "@/store/auth";
import { Button } from "@/components/ui/button";
import {
  LayoutDashboard,
  Users,
  Package,
  CreditCard,
  Settings,
  LogOut,
  PanelLeftClose,
  PanelLeft,
} from "lucide-react";
import { t } from "@/i18n";
import { SupportBanner } from "@/features/admin/components/support-banner";

export function AdminLayout() {
  const { username, logout, role, tenantPlan, isMasterSupportContext } = useAuthStore();
  const location = useLocation();
  const [collapsed, setCollapsed] = useState(false);

  const isStarterTenantAdmin = role === "tenant" && tenantPlan === "starter";
  const showProNav = !isStarterTenantAdmin || isMasterSupportContext;

  const NAV_ITEMS = [
    { to: "/admin/dashboard", label: t("frontend.dashboard.tenant.title"), icon: LayoutDashboard, proOnly: false },
    { to: "/admin/clients", label: t("frontend.clients.section_title"), icon: Users, proOnly: true },
    { to: "/admin/catalog", label: t("frontend.catalog.section_title"), icon: Package, proOnly: true },
    { to: "/admin/subscriptions", label: t("frontend.subscriptions.title"), icon: CreditCard, proOnly: true },
    { to: "/admin/settings", label: t("frontend.settings.section_title"), icon: Settings, proOnly: false },
  ].filter((item) => showProNav || !item.proOnly);

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
            const isActive = location.pathname.startsWith(item.to);
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
            {!collapsed && <span>{t("frontend.dashboard.tenant.logout")}</span>}
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
        {isMasterSupportContext && tenantPlan === "starter" && <SupportBanner />}
        <Outlet />
      </main>
    </div>
  );
}
