import { useState, useEffect, useCallback } from "react";
import { useAuthStore } from "@/store/auth";
import { Navigate } from "@tanstack/react-router";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import {
  User,
  CreditCard,
  LogOut,
  Mail,
  Phone,
  Building2,
  AlertCircle,
} from "lucide-react";
import { t } from "@/i18n";
import {
  fetchClientDashboard,
  type ClientDashboardData,
  type ClientActiveSubscription,
} from "../services/client-dashboard-api";

/* ── Helpers ────────────────────────────────────────────────── */

function formatDate(iso: string): string {
  return new Date(iso).toLocaleDateString("en-US", {
    year: "numeric",
    month: "short",
    day: "numeric",
  });
}

function daysUntil(iso: string): number {
  const diff = new Date(iso).getTime() - Date.now();
  return Math.ceil(diff / (1000 * 60 * 60 * 24));
}

function StatusBadge({ active }: { active: boolean }) {
  return (
    <Badge
      variant={active ? "default" : "secondary"}
      className={
        active
          ? "bg-emerald-100 text-emerald-800 hover:bg-emerald-100 dark:bg-emerald-900 dark:text-emerald-300"
          : "bg-amber-100 text-amber-800 hover:bg-amber-100 dark:bg-amber-900 dark:text-amber-300"
      }
    >
      {t(active ? "frontend.dashboard.client.status_active" : "frontend.dashboard.client.status_inactive")}
    </Badge>
  );
}

function SubscriptionStatusBadge({ status }: { status: string }) {
  const variants: Record<string, string> = {
    active: "bg-emerald-100 text-emerald-800 hover:bg-emerald-100 dark:bg-emerald-900 dark:text-emerald-300",
    expired: "bg-amber-100 text-amber-800 hover:bg-amber-100 dark:bg-amber-900 dark:text-amber-300",
    cancelled: "bg-destructive/10 text-destructive hover:bg-destructive/10",
  };

  return (
    <Badge variant="secondary" className={variants[status] || "bg-muted text-muted-foreground"}>
      {status}
    </Badge>
  );
}

/* ── Subscription Table ─────────────────────────────────────── */

function SubscriptionTable({ subscriptions }: { subscriptions: ClientActiveSubscription[] }) {
  if (subscriptions.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center py-12 text-center">
        <CreditCard className="size-10 text-muted-foreground/50 mb-3" />
        <p className="text-sm font-medium text-muted-foreground">
          No active subscriptions
        </p>
        <p className="text-xs text-muted-foreground mt-1">
          Your subscriptions will appear here once assigned.
        </p>
      </div>
    );
  }

  return (
    <>
      {/* Desktop table */}
      <div className="hidden md:block overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="bg-muted/50">
              <th className="text-left p-3 font-medium">Service</th>
              <th className="text-left p-3 font-medium">Plan</th>
              <th className="text-left p-3 font-medium">Status</th>
              <th className="text-left p-3 font-medium">Start</th>
              <th className="text-left p-3 font-medium">Expires</th>
            </tr>
          </thead>
          <tbody>
            {subscriptions.map((sub) => {
              const remaining = daysUntil(sub.expires_at);
              return (
                <tr
                  key={sub.id}
                  className="border-t hover:bg-muted/30 transition-colors"
                >
                  <td className="p-3 font-medium">{sub.service_name}</td>
                  <td className="p-3">{sub.plan_name}</td>
                  <td className="p-3">
                    <SubscriptionStatusBadge status={sub.status} />
                  </td>
                  <td className="p-3 text-muted-foreground">
                    {formatDate(sub.starts_at)}
                  </td>
                  <td className="p-3">
                    <span className="text-muted-foreground">
                      {formatDate(sub.expires_at)}
                    </span>
                    {sub.status === "active" && remaining <= 7 && remaining > 0 && (
                      <span className="ml-2 text-xs text-amber-600 dark:text-amber-400">
                        ({remaining}d left)
                      </span>
                    )}
                    {sub.status === "active" && remaining <= 0 && (
                      <span className="ml-2 text-xs text-destructive">
                        (expired)
                      </span>
                    )}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>

      {/* Mobile cards */}
      <div className="md:hidden divide-y">
        {subscriptions.map((sub) => {
          const remaining = daysUntil(sub.expires_at);
          return (
            <div key={sub.id} className="p-4 space-y-2">
              <div className="flex items-start justify-between">
                <div>
                  <p className="font-medium">{sub.service_name}</p>
                  <p className="text-sm text-muted-foreground">{sub.plan_name}</p>
                </div>
                <SubscriptionStatusBadge status={sub.status} />
              </div>
              <div className="text-sm text-muted-foreground">
                <p>
                  {formatDate(sub.starts_at)} → {formatDate(sub.expires_at)}
                  {sub.status === "active" && remaining <= 7 && remaining > 0 && (
                    <span className="ml-1 text-amber-600 dark:text-amber-400">
                      ({remaining}d left)
                    </span>
                  )}
                </p>
              </div>
            </div>
          );
        })}
      </div>
    </>
  );
}

/* ── Dashboard Page ─────────────────────────────────────────── */

export function DashboardPage() {
  const { isAuthenticated, role, logout } = useAuthStore();

  const [dashboard, setDashboard] = useState<ClientDashboardData | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState("");

  const loadDashboard = useCallback(async () => {
    setIsLoading(true);
    setError("");
    try {
      const data = await fetchClientDashboard();
      setDashboard(data);
    } catch (err) {
      setError(
        err instanceof Error ? err.message : "Unable to load dashboard"
      );
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    loadDashboard();
  }, [loadDashboard]);

  if (!isAuthenticated || role !== "client") {
    return <Navigate to="/login" replace />;
  }

  return (
    <div className="flex-1 overflow-auto">
      <div className="max-w-5xl mx-auto px-4 sm:px-6 py-6 flex flex-col gap-6">
        {/* ── Loading state ─────────────────────────────────── */}
        {isLoading && (
          <>
            <div className="flex items-center justify-between">
              <div className="space-y-2">
                <Skeleton className="h-8 w-64" />
                <Skeleton className="h-4 w-48" />
              </div>
              <Skeleton className="h-9 w-24" />
            </div>
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
              {Array.from({ length: 3 }).map((_, i) => (
                <Skeleton key={i} className="h-24 rounded-xl" />
              ))}
            </div>
            <Skeleton className="h-64 rounded-xl" />
          </>
        )}

        {/* ── Error state ───────────────────────────────────── */}
        {!isLoading && error && (
          <div className="rounded-lg bg-destructive/10 border border-destructive/20 p-4 text-sm text-destructive flex items-start gap-3">
            <AlertCircle className="size-4 mt-0.5 shrink-0" />
            <div>
              <p className="font-medium">Failed to load dashboard</p>
              <p className="mt-1">{error}</p>
              <Button
                variant="outline"
                size="sm"
                className="mt-3"
                onClick={loadDashboard}
              >
                Retry
              </Button>
            </div>
          </div>
        )}

        {/* ── Content ───────────────────────────────────────── */}
        {!isLoading && !error && dashboard && (
          <>
            {/* Header */}
            <div className="flex items-start justify-between gap-4">
              <div>
                <h1 className="text-2xl font-bold tracking-tight">
                  {t("frontend.dashboard.client.title")}
                </h1>
                <p className="text-muted-foreground">
                  {t("frontend.dashboard.client.welcome", { name: dashboard.full_name })}
                </p>
              </div>
              <Button variant="outline" size="sm" onClick={() => logout()}>
                <LogOut className="size-4 mr-2" />
                Logout
              </Button>
            </div>

            {/* Summary cards */}
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
              <Card>
                <CardContent className="flex items-center gap-4 p-5">
                  <div className="flex size-10 shrink-0 items-center justify-center rounded-lg bg-muted">
                    <User className="size-5 text-muted-foreground" />
                  </div>
                  <div className="min-w-0">
                    <p className="text-sm text-muted-foreground">Account</p>
                    <p className="text-lg font-bold tracking-tight truncate">
                      {dashboard.username}
                    </p>
                  </div>
                </CardContent>
              </Card>

              <Card>
                <CardContent className="flex items-center gap-4 p-5">
                  <div className="flex size-10 shrink-0 items-center justify-center rounded-lg bg-muted">
                    <Building2 className="size-5 text-muted-foreground" />
                  </div>
                  <div className="min-w-0">
                    <p className="text-sm text-muted-foreground">Provider</p>
                    <p className="text-lg font-bold tracking-tight truncate">
                      {dashboard.tenant_name || "—"}
                    </p>
                  </div>
                </CardContent>
              </Card>

              <Card>
                <CardContent className="flex items-center gap-4 p-5">
                  <div className="flex size-10 shrink-0 items-center justify-center rounded-lg bg-muted">
                    <CreditCard className="size-5 text-muted-foreground" />
                  </div>
                  <div className="min-w-0">
                    <p className="text-sm text-muted-foreground">Subscriptions</p>
                    <p className="text-lg font-bold tracking-tight">
                      {dashboard.subscriptions.length}
                    </p>
                  </div>
                </CardContent>
              </Card>
            </div>

            {/* Info strip */}
            <div className="flex flex-wrap items-center gap-4 text-sm text-muted-foreground">
              <div className="flex items-center gap-2">
                <Mail className="size-4" />
                <span>{dashboard.username}</span>
              </div>
              {dashboard.phone && (
                <div className="flex items-center gap-2">
                  <Phone className="size-4" />
                  <span>{dashboard.phone}</span>
                </div>
              )}
              <StatusBadge active={dashboard.is_active} />
            </div>

            {/* Subscriptions */}
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2 text-base">
                  <CreditCard className="size-5 text-muted-foreground" />
                  Subscriptions
                </CardTitle>
              </CardHeader>
              <CardContent className="p-0">
                <SubscriptionTable subscriptions={dashboard.subscriptions} />
              </CardContent>
            </Card>

            {/* Read-only notice */}
            <p className="text-xs text-muted-foreground text-center">
              {t("frontend.dashboard.client.readonly")}
            </p>
          </>
        )}
      </div>
    </div>
  );
}
