import { useState, useEffect, useCallback } from "react";
import { useNavigate } from "@tanstack/react-router";
import { useAuthStore } from "@/store/auth";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Switch } from "@/components/ui/switch";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { Sheet, SheetContent, SheetTrigger } from "@/components/ui/sheet";
import { NavItem } from "./sidebar-nav";
import { fetchCodeServices, saveCodeServices, type CodeService } from "@/features/master/services/tenant-api";
import { toast } from "sonner";
import {
  LayoutDashboard,
  Settings,
  LogOut,
  ChevronLeft,
  ChevronRight,
  Save,
  Menu,
} from "lucide-react";
import { cn } from "@/lib/utils";

/* ── Code Services Dialog ──────────────────────────────────────── */

function CodeServicesDialog({
  open,
  onOpenChange,
}: {
  open: boolean
  onOpenChange: (open: boolean) => void
}) {
  const [services, setServices] = useState<CodeService[]>([]);
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);

  const loadServices = useCallback(async () => {
    setLoading(true);
    try {
      const data = await fetchCodeServices();
      setServices(data);
    } catch {
      toast.error("Unable to load code services");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (open) loadServices();
  }, [open, loadServices]);

  function toggleService(key: string) {
    setServices((prev) =>
      prev.map((svc) =>
        svc.service_key === key ? { ...svc, is_active: !svc.is_active } : svc
      )
    );
  }

  async function handleSave() {
    setSaving(true);
    try {
      const payload: Record<string, boolean> = {};
      for (const svc of services) {
        payload[svc.service_key] = svc.is_active;
      }
      await saveCodeServices(payload);
      toast.success("Code services saved");
      onOpenChange(false);
    } catch {
      toast.error("Unable to save code services");
    } finally {
      setSaving(false);
    }
  }

  const activeCount = services.filter((s) => s.is_active).length;

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>Code Services</DialogTitle>
          <DialogDescription>
            Configure which services are enabled globally for all tenants.
          </DialogDescription>
        </DialogHeader>

        <div className="py-4">
          {loading ? (
            <div className="flex flex-col gap-3">
              {[1, 2, 3].map((i) => (
                <Skeleton key={i} className="h-14 w-full rounded-lg" />
              ))}
            </div>
          ) : services.length === 0 ? (
            <p className="text-sm text-muted-foreground text-center py-8">
              No code services available.
            </p>
          ) : (
            <div className="flex flex-col gap-1">
              {services.map((svc) => (
                <div
                  key={svc.service_key}
                  className="flex items-center justify-between gap-3 rounded-lg p-3 hover:bg-muted/50 transition-colors"
                >
                  <div className="flex items-center gap-3">
                    <span className="font-medium text-sm">{svc.label}</span>
                    <Badge
                      variant={svc.is_active ? "default" : "secondary"}
                      className={
                        svc.is_active
                          ? "bg-emerald-100 text-emerald-800 dark:bg-emerald-900 dark:text-emerald-300"
                          : "bg-muted text-muted-foreground"
                      }
                    >
                      {svc.is_active ? "Active" : "Inactive"}
                    </Badge>
                  </div>
                  <Switch
                    checked={svc.is_active}
                    onCheckedChange={() => toggleService(svc.service_key)}
                  />
                </div>
              ))}
            </div>
          )}
        </div>

        <DialogFooter>
          <div className="flex items-center justify-between w-full">
            <span className="text-sm text-muted-foreground">
              {activeCount} of {services.length} active
            </span>
            <Button onClick={handleSave} disabled={saving || loading}>
              <Save className="size-4 mr-2" />
              {saving ? "Saving..." : "Save Changes"}
            </Button>
          </div>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

/* ── Sidebar Content ───────────────────────────────────────────── */

interface SidebarContentProps {
  collapsed?: boolean
  onToggleCollapse?: () => void
  onCodeServices?: () => void
  onCloseMobile?: () => void
}

export function SidebarContent({
  collapsed,
  onToggleCollapse,
  onCodeServices,
  onCloseMobile,
}: SidebarContentProps) {
  const navigate = useNavigate();
  const { username, logout } = useAuthStore();

  async function handleLogout() {
    await logout();
    await navigate({ to: "/login" });
    onCloseMobile?.();
  }

  return (
    <div className="flex h-full flex-col">
      {/* Logo */}
      <div className="h-14 flex items-center px-4 border-b shrink-0">
        <span
          className={cn(
            "font-bold tracking-tight text-primary transition-all",
            collapsed ? "text-lg" : "text-xl"
          )}
        >
          {collapsed ? "TP" : "TrackPal"}
        </span>
      </div>

      {/* Navigation */}
      <nav className="flex-1 p-2 flex flex-col gap-1">
        <NavItem
          icon={<LayoutDashboard className="size-4 shrink-0" />}
          label="Dashboard"
          collapsed={collapsed}
          active
          onClick={() => {
            window.location.href = "/master/dashboard";
            onCloseMobile?.();
          }}
        />
        <NavItem
          icon={<Settings className="size-4 shrink-0" />}
          label="Code Services"
          collapsed={collapsed}
          onClick={() => {
            onCodeServices?.();
            onCloseMobile?.();
          }}
        />
      </nav>

      {/* Bottom section */}
      <div className="p-2 border-t flex flex-col gap-1">
        {onToggleCollapse && (
          <NavItem
            icon={
              collapsed ? (
                <ChevronRight className="size-4 shrink-0" />
              ) : (
                <ChevronLeft className="size-4 shrink-0" />
              )
            }
            label="Collapse"
            collapsed={collapsed}
            onClick={onToggleCollapse}
          />
        )}

        {!collapsed && (
          <div className="px-3 py-2">
            <span className="text-sm text-muted-foreground truncate block">
              {username || "Master"}
            </span>
          </div>
        )}

        <NavItem
          icon={<LogOut className="size-4 shrink-0" />}
          label="Logout"
          collapsed={collapsed}
          onClick={handleLogout}
        />
      </div>
    </div>
  );
}

/* ── Desktop Sidebar ───────────────────────────────────────────── */

export function AppSidebar() {
  const [collapsed, setCollapsed] = useState(false);
  const [codeServicesOpen, setCodeServicesOpen] = useState(false);

  return (
    <>
      <aside
        className={cn(
          "hidden md:flex flex-col border-r bg-card transition-all duration-200 shrink-0",
          collapsed ? "w-[60px]" : "w-[220px]"
        )}
      >
        <SidebarContent
          collapsed={collapsed}
          onToggleCollapse={() => setCollapsed((c) => !c)}
          onCodeServices={() => setCodeServicesOpen(true)}
        />
      </aside>

      <CodeServicesDialog
        open={codeServicesOpen}
        onOpenChange={setCodeServicesOpen}
      />
    </>
  );
}

/* ── Mobile Sidebar (Sheet) ────────────────────────────────────── */

export function MobileSidebar() {
  const [open, setOpen] = useState(false);
  const [codeServicesOpen, setCodeServicesOpen] = useState(false);

  return (
    <>
      <div className="md:hidden flex items-center gap-3 h-14 px-4 border-b">
        <Sheet open={open} onOpenChange={setOpen}>
          <SheetTrigger asChild>
            <Button variant="ghost" size="icon" className="shrink-0">
              <Menu className="size-5" />
              <span className="sr-only">Toggle menu</span>
            </Button>
          </SheetTrigger>
          <SheetContent side="left" className="w-[240px] p-0">
            <SidebarContent
              onCodeServices={() => {
                setOpen(false);
                setCodeServicesOpen(true);
              }}
              onCloseMobile={() => setOpen(false)}
            />
          </SheetContent>
        </Sheet>
        <span className="font-bold tracking-tight text-primary">TrackPal</span>
      </div>

      <CodeServicesDialog
        open={codeServicesOpen}
        onOpenChange={setCodeServicesOpen}
      />
    </>
  );
}
