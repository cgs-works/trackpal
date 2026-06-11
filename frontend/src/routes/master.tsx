import { createFileRoute, Outlet, Navigate, useNavigate } from "@tanstack/react-router";
import { useState, useEffect, useCallback } from "react";
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
import api from "@/lib/api";
import { toast } from "sonner";
import {
  LayoutDashboard,
  Settings,
  LogOut,
  ChevronLeft,
  ChevronRight,
  Save,
} from "lucide-react";
import { cn } from "@/lib/utils";

export const Route = createFileRoute("/master")({
  component: MasterLayout,
});

interface CodeService {
  service_key: string;
  label: string;
  is_active: boolean;
}

function MasterLayout() {
  const navigate = useNavigate();
  const { username, logout, isAuthenticated, role } = useAuthStore();
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);
  const [codeServicesOpen, setCodeServicesOpen] = useState(false);
  const [services, setServices] = useState<CodeService[]>([]);
  const [servicesLoading, setServicesLoading] = useState(false);
  const [servicesSaving, setServicesSaving] = useState(false);

  if (!isAuthenticated || role !== "master") {
    return <Navigate to="/login" replace />;
  }

  async function handleLogout() {
    await logout();
    await navigate({ to: "/login" });
  }

  const loadServices = useCallback(async () => {
    setServicesLoading(true);
    try {
      const res = await api.get<{ services: CodeService[] }>("/code-services/global");
      setServices(res.data.services || []);
    } catch {
      toast.error("Unable to load code services");
    } finally {
      setServicesLoading(false);
    }
  }, []);

  useEffect(() => {
    if (codeServicesOpen) {
      loadServices();
    }
  }, [codeServicesOpen, loadServices]);

  function toggleService(key: string) {
    setServices((prev) =>
      prev.map((svc) =>
        svc.service_key === key ? { ...svc, is_active: !svc.is_active } : svc
      )
    );
  }

  async function saveServices() {
    setServicesSaving(true);
    try {
      const payload: Record<string, boolean> = {};
      for (const svc of services) {
        payload[svc.service_key] = svc.is_active;
      }
      await api.put("/code-services/global", { services: payload });
      toast.success("Code services saved");
      setCodeServicesOpen(false);
    } catch (error) {
      toast.error("Unable to save code services");
    } finally {
      setServicesSaving(false);
    }
  }

  const activeCount = services.filter((s) => s.is_active).length;

  return (
    <div className="min-h-screen flex bg-background">
      {/* Sidebar */}
      <aside
        className={cn(
          "flex flex-col border-r bg-card transition-all duration-200",
          sidebarCollapsed ? "w-[60px]" : "w-[220px]"
        )}
      >
        {/* Logo */}
        <div className="h-14 flex items-center px-4 border-b">
          <span
            className={cn(
              "font-bold tracking-tight text-primary transition-all",
              sidebarCollapsed ? "text-lg" : "text-xl"
            )}
          >
            {sidebarCollapsed ? "TP" : "TrackPal"}
          </span>
        </div>

        {/* Navigation */}
        <nav className="flex-1 p-2 space-y-1">
          <a
            href="/master/dashboard"
            className={cn(
              "flex items-center gap-3 px-3 py-2 rounded-md text-sm font-medium transition-colors",
              "bg-accent text-accent-foreground"
            )}
          >
            <LayoutDashboard className="h-4 w-4 shrink-0" />
            {!sidebarCollapsed && <span>Dashboard</span>}
          </a>

          <button
            onClick={() => setCodeServicesOpen(true)}
            className="flex items-center gap-3 px-3 py-2 rounded-md text-sm font-medium text-muted-foreground hover:bg-accent hover:text-accent-foreground transition-colors w-full"
          >
            <Settings className="h-4 w-4 shrink-0" />
            {!sidebarCollapsed && <span>Code Services</span>}
          </button>
        </nav>

        {/* Bottom section */}
        <div className="p-2 border-t space-y-1">
          <button
            onClick={() => setSidebarCollapsed(!sidebarCollapsed)}
            className="flex items-center gap-3 px-3 py-2 rounded-md text-sm text-muted-foreground hover:bg-accent hover:text-accent-foreground transition-colors w-full"
          >
            {sidebarCollapsed ? (
              <ChevronRight className="h-4 w-4 shrink-0" />
            ) : (
              <ChevronLeft className="h-4 w-4 shrink-0" />
            )}
            {!sidebarCollapsed && <span>Collapse</span>}
          </button>

          <div className="flex items-center gap-3 px-3 py-2">
            {!sidebarCollapsed && (
              <span className="text-sm text-muted-foreground truncate">
                {username || "Master"}
              </span>
            )}
          </div>

          <button
            onClick={handleLogout}
            className="flex items-center gap-3 px-3 py-2 rounded-md text-sm text-muted-foreground hover:bg-accent hover:text-accent-foreground transition-colors w-full"
          >
            <LogOut className="h-4 w-4 shrink-0" />
            {!sidebarCollapsed && <span>Logout</span>}
          </button>
        </div>
      </aside>

      {/* Main content */}
      <div className="flex-1 flex flex-col min-h-screen overflow-hidden">
        <Outlet />
      </div>

      {/* Code Services Modal */}
      <Dialog open={codeServicesOpen} onOpenChange={setCodeServicesOpen}>
        <DialogContent className="sm:max-w-md">
          <DialogHeader>
            <DialogTitle>Code Services</DialogTitle>
            <DialogDescription>
              Configure which services are enabled globally for all tenants.
            </DialogDescription>
          </DialogHeader>

          <div className="py-4">
            {servicesLoading ? (
              <div className="space-y-3">
                {[1, 2, 3].map((i) => (
                  <Skeleton key={i} className="h-14 w-full rounded-lg" />
                ))}
              </div>
            ) : services.length === 0 ? (
              <p className="text-sm text-muted-foreground text-center py-8">
                No code services available.
              </p>
            ) : (
              <div className="space-y-1">
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
              <Button
                onClick={saveServices}
                disabled={servicesSaving || servicesLoading}
              >
                <Save className="h-4 w-4 mr-2" />
                {servicesSaving ? "Saving..." : "Save Changes"}
              </Button>
            </div>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
