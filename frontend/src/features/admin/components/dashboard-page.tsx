import { useCallback, useEffect, useState } from "react";
import { Navigate } from "@tanstack/react-router";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { useAuthStore } from "@/store/auth";
import { t } from "@/i18n";
import { getTenantDashboard, type TenantDashboardResponse } from "../services/dashboard-api";
import { getApiError } from "@/lib/api-errors";
import { Ban, CheckCircle2, Database, LogOut, Mail, Package, Users } from "lucide-react";

function MetricCard({ title, value, icon: Icon }: { title: string; value: string | number; icon: typeof Users }) {
  return (
    <Card className="shadow-none">
      <CardHeader className="flex flex-row items-center justify-between pb-2">
        <CardTitle className="text-sm font-medium">{title}</CardTitle>
        <span className="flex size-9 items-center justify-center rounded-lg border bg-primary/8 text-primary">
          <Icon className="size-4" />
        </span>
      </CardHeader>
      <CardContent>
        <div className="font-mono text-2xl font-semibold tracking-tight">{value}</div>
      </CardContent>
    </Card>
  );
}

export function DashboardPage() {
  const { isAuthenticated, role, username, logout, setTenantPlan } = useAuthStore();
  const [dashboard, setDashboard] = useState<TenantDashboardResponse | null>(null);
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const data = await getTenantDashboard();
      setDashboard(data);
      if (data.tenant_plan !== useAuthStore.getState().tenantPlan) {
        setTenantPlan(data.tenant_plan);
      }
    } catch (error) {
      toast.error(getApiError(error, t("frontend.dashboard.error_load")));
    } finally {
      setLoading(false);
    }
  }, [setTenantPlan]);

  useEffect(() => {
    if (isAuthenticated) load();
  }, [isAuthenticated, load]);

  // ponytail: master needs access to view tenant dashboards in support mode
  if (!isAuthenticated || (role !== "tenant" && role !== "master")) {
    return <Navigate to="/login" replace />;
  }

  if (loading || !dashboard) {
    return (
      <div className="mx-auto flex max-w-6xl flex-col gap-6 p-4 sm:p-6 lg:p-8" aria-label={t("frontend.dashboard.loading")}>
        <div className="flex flex-col gap-2">
          <Skeleton className="h-8 w-64" />
          <Skeleton className="h-4 w-80 max-w-full" />
        </div>
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          {Array.from({ length: 4 }).map((_, index) => <Skeleton key={index} className="h-32 rounded-xl" />)}
        </div>
      </div>
    );
  }

  const isPro = dashboard.tenant_plan === "pro";
  const planLabel = isPro ? "Pro" : "Starter";

  return (
    <div className="flex-1 p-4 sm:p-6 lg:p-8">
      <div className="mx-auto flex max-w-6xl flex-col gap-6">
        <div className="flex items-center justify-between gap-4">
          <div className="flex flex-col gap-1">
            <div className="flex items-center gap-2">
              <h1 className="font-heading text-2xl font-semibold tracking-tight">{t("frontend.dashboard.tenant.title")}</h1>
              <Badge variant={isPro ? "default" : "secondary"}>{planLabel}</Badge>
            </div>
            <p className="text-muted-foreground">{t("frontend.dashboard.tenant.welcome", { name: username || "Admin" })}</p>
          </div>
          <Button variant="outline" size="sm" onClick={() => logout()}>
            <LogOut data-icon="inline-start" />
            {t("frontend.dashboard.tenant.logout")}
          </Button>
        </div>

        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          <MetricCard title={t("frontend.dashboard.plan")} value={planLabel} icon={CheckCircle2} />
          <MetricCard title={t("frontend.mailbox.section_title")} value={dashboard.mailbox_status} icon={Mail} />
          <MetricCard title={t("frontend.code_services.tenant_section_title")} value={dashboard.enabled_code_services.length} icon={Package} />
          <MetricCard title={t("frontend.access_control.section_title")} value={dashboard.access_control_count} icon={Ban} />
        </div>

        {dashboard.enabled_code_services.length > 0 && (
          <Card>
            <CardHeader><CardTitle>{t("frontend.code_services.tenant_section_title")}</CardTitle></CardHeader>
            <CardContent className="flex flex-wrap gap-2">
              {dashboard.enabled_code_services.map((service) => <Badge key={service} variant="secondary">{service}</Badge>)}
            </CardContent>
          </Card>
        )}

        {isPro && (
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
            <MetricCard title={t("frontend.clients.section_title")} value={dashboard.active_clients ?? 0} icon={Users} />
            <MetricCard title={t("frontend.catalog.section_title")} value={dashboard.catalog_services ?? 0} icon={Database} />
            <MetricCard title={t("frontend.subscriptions.title")} value={dashboard.active_subscriptions ?? 0} icon={CheckCircle2} />
            <MetricCard title={t("frontend.dashboard.expiring_soon")} value={dashboard.subscriptions_expiring_soon ?? 0} icon={Mail} />
          </div>
        )}
      </div>
    </div>
  );
}
