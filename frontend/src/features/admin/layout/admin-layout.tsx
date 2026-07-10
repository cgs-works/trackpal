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
import { BrandLogo } from "@/components/layout/brand-logo";

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
    <div className="flex h-screen bg-background/80">
      {/* ── Sidebar ──────────────────────────────────────────── */}
      <aside
        className={`hidden flex-col border-r border-border bg-sidebar transition-[width] duration-200 md:flex ${
          collapsed ? "w-16" : "w-60"
        }`}
      >
        {/* Brand */}
        <div className="flex h-16 items-center gap-2 border-b border-border px-4">
          {!collapsed && <BrandLogo />}
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
        <nav className="flex flex-1 flex-col gap-1 p-2">
          {NAV_ITEMS.map((item) => {
            const isActive = location.pathname.startsWith(item.to);
            return (
              <Link
                key={item.to}
                to={item.to}
                className={`flex min-h-10 items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium transition-colors duration-200 ${
                  isActive
                    ? "bg-sidebar-primary text-sidebar-primary-foreground shadow-[0_0_22px_-12px_var(--sidebar-primary)]"
                    : "text-muted-foreground hover:bg-sidebar-accent hover:text-sidebar-accent-foreground"
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
      <div className="fixed inset-x-0 top-0 z-40 flex h-16 items-center gap-3 border-b border-border bg-sidebar/95 px-4 backdrop-blur-xl md:hidden">
        <BrandLogo />
        <div className="ml-auto flex items-center gap-2">
          <span className="text-sm text-muted-foreground">{username}</span>
          <Button variant="ghost" size="icon" onClick={() => logout()}>
            <LogOut className="size-4" />
          </Button>
        </div>
      </div>

      {/* ── Main content ─────────────────────────────────────── */}
      <main className="flex-1 overflow-y-auto pt-16 md:pt-0">
        {isMasterSupportContext && tenantPlan === "starter" && <SupportBanner />}
        <Outlet />
      </main>
    </div>
  );
}
