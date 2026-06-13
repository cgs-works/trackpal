import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Pencil, Eye, MoreHorizontal, Ban, RotateCcw, RefreshCw } from "lucide-react";
import { t } from "@/i18n";
import { type Subscription } from "../services/subscription-api";
import { SubscriptionStatusBadge } from "@/components/subscription-status-badge";

interface SubscriptionTableProps {
  subscriptions: Subscription[];
  clients: Record<string, string>;
  services: Record<string, string>;
  plans: Record<string, string>;
  onEdit: (sub: Subscription) => void;
  onReveal: (sub: Subscription) => void;
  onCancel: (sub: Subscription) => void;
  onRenew: (sub: Subscription) => void;
  onReactivate: (sub: Subscription) => void;
}

function formatDate(iso: string): string {
  return new Date(iso).toLocaleDateString("en-US", {
    year: "numeric",
    month: "short",
    day: "numeric",
  });
}

export function SubscriptionTable({
  subscriptions,
  clients,
  services,
  plans,
  onEdit,
  onReveal,
  onCancel,
  onRenew,
  onReactivate,
}: SubscriptionTableProps) {
  return (
    <>
      {/* Desktop table */}
      <div className="hidden md:block rounded-lg border overflow-hidden">
        <table className="w-full text-sm">
          <thead>
            <tr className="bg-muted/50">
              <th className="text-left p-3 font-medium">{t("frontend.subscriptions.client")}</th>
              <th className="text-left p-3 font-medium">{t("frontend.subscriptions.service")}</th>
              <th className="text-left p-3 font-medium">{t("frontend.subscriptions.plan")}</th>
              <th className="text-left p-3 font-medium">{t("frontend.subscriptions.email")}</th>
              <th className="text-left p-3 font-medium">{t("frontend.subscriptions.status")}</th>
              <th className="text-left p-3 font-medium">{t("frontend.subscriptions.start")}</th>
              <th className="text-left p-3 font-medium">{t("frontend.subscriptions.end")}</th>
              <th className="text-right p-3 font-medium">{t("frontend.subscriptions.actions")}</th>
            </tr>
          </thead>
          <tbody>
            {subscriptions.map((sub) => (
              <tr
                key={sub.id}
                className="border-t hover:bg-muted/30 transition-colors"
              >
                <td className="p-3 font-medium">
                  {clients[sub.client_id] || "—"}
                </td>
                <td className="p-3">
                  {services[sub.service_id] || "—"}
                </td>
                <td className="p-3">
                  {plans[sub.plan_id] || "—"}
                </td>
                <td className="p-3 font-mono text-xs">
                  {sub.streaming_email}
                </td>
                <td className="p-3">
                  <SubscriptionStatusBadge status={sub.status} />
                </td>
                <td className="p-3 text-muted-foreground">
                  {formatDate(sub.starts_at)}
                </td>
                <td className="p-3 text-muted-foreground">
                  {formatDate(sub.expires_at)}
                </td>
                <td className="p-3 text-right">
                  <div className="flex items-center justify-end gap-1">
                    <Button
                      variant="ghost"
                      size="icon"
                      className="size-8"
                      title={t("frontend.subscriptions.reveal")}
                      onClick={() => onReveal(sub)}
                    >
                      <Eye className="size-4" />
                    </Button>
                    <Button
                      variant="ghost"
                      size="icon"
                      className="size-8"
                      title={t("frontend.common.edit")}
                      onClick={() => onEdit(sub)}
                    >
                      <Pencil className="size-4" />
                    </Button>
                    <DropdownMenu>
                      <DropdownMenuTrigger
                        render={
                          <Button
                            variant="ghost"
                            size="icon"
                            className="size-8"
                            title={t("frontend.subscriptions.more_actions")}
                          />
                        }
                      >
                        <MoreHorizontal className="size-4" />
                      </DropdownMenuTrigger>
                      <DropdownMenuContent align="end">
                        {(sub.status === "active" || sub.status === "expired") && (
                          <DropdownMenuItem onClick={() => onRenew(sub)}>
                            <RefreshCw className="size-4" />
                            {t("frontend.subscriptions.renew")}
                          </DropdownMenuItem>
                        )}
                        {(sub.status === "cancelled" || sub.status === "expired") && (
                          <DropdownMenuItem onClick={() => onReactivate(sub)}>
                            <RotateCcw className="size-4" />
                            {t("frontend.subscriptions.reactivate")}
                          </DropdownMenuItem>
                        )}
                        {sub.status === "active" && (
                          <>
                            <DropdownMenuSeparator />
                            <DropdownMenuItem
                              variant="destructive"
                              onClick={() => onCancel(sub)}
                            >
                              <Ban className="size-4" />
                              {t("frontend.subscriptions.cancel_action")}
                            </DropdownMenuItem>
                          </>
                        )}
                      </DropdownMenuContent>
                    </DropdownMenu>
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* Mobile cards */}
      <div className="md:hidden space-y-3">
        {subscriptions.map((sub) => (
          <div key={sub.id} className="rounded-lg border bg-card p-4 space-y-3">
            <div className="flex items-start justify-between">
              <div>
                <p className="font-medium">{clients[sub.client_id] || "—"}</p>
                <p className="text-sm text-muted-foreground">
                  {services[sub.service_id] || "—"} · {plans[sub.plan_id] || "—"}
                </p>
              </div>
              <SubscriptionStatusBadge status={sub.status} />
            </div>
            <div className="text-sm space-y-1">
              <p className="font-mono text-xs text-muted-foreground">
                {sub.streaming_email}
              </p>
              <p className="text-muted-foreground">
                {formatDate(sub.starts_at)} → {formatDate(sub.expires_at)}
              </p>
            </div>
            <div className="flex gap-2">
              <Button
                variant="outline"
                size="sm"
                className="flex-1"
                onClick={() => onReveal(sub)}
              >
                <Eye className="size-3.5 mr-1" />
                {t("frontend.subscriptions.reveal")}
              </Button>
              <Button
                variant="outline"
                size="sm"
                className="flex-1"
                onClick={() => onEdit(sub)}
              >
                <Pencil className="size-3.5 mr-1" />
                {t("frontend.common.edit")}
              </Button>
              <DropdownMenu>
                <DropdownMenuTrigger
                  render={
                    <Button
                      variant="outline"
                      size="sm"
                    />
                  }
                >
                  <MoreHorizontal className="size-3.5" />
                </DropdownMenuTrigger>
                <DropdownMenuContent align="end">
                  {(sub.status === "active" || sub.status === "expired") && (
                    <DropdownMenuItem onClick={() => onRenew(sub)}>
                      <RefreshCw className="size-4" />
                      {t("frontend.subscriptions.renew")}
                    </DropdownMenuItem>
                  )}
                  {(sub.status === "cancelled" || sub.status === "expired") && (
                    <DropdownMenuItem onClick={() => onReactivate(sub)}>
                      <RotateCcw className="size-4" />
                      {t("frontend.subscriptions.reactivate")}
                    </DropdownMenuItem>
                  )}
                  {sub.status === "active" && (
                    <>
                      <DropdownMenuSeparator />
                      <DropdownMenuItem
                        variant="destructive"
                        onClick={() => onCancel(sub)}
                      >
                        <Ban className="size-4" />
                        {t("frontend.subscriptions.cancel_action")}
                      </DropdownMenuItem>
                    </>
                  )}
                </DropdownMenuContent>
              </DropdownMenu>
            </div>
          </div>
        ))}
      </div>
    </>
  );
}

// ── Credentials reveal dialog ──────────────────────────────────
interface RevealCredentialsDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  email: string;
  password: string | null;
  pin: string | null;
}

export function RevealCredentialsDialog({
  open,
  onOpenChange,
  email,
  password,
  pin,
}: RevealCredentialsDialogProps) {
  if (!open) return null;

  return (
    <div className="fixed inset-0 z-50">
      {/* Backdrop */}
      <div
        className="absolute inset-0 bg-background/80 backdrop-blur-sm"
        onClick={() => onOpenChange(false)}
      />
      {/* Content */}
      <div className="absolute inset-0 flex items-center justify-center p-4">
        <div className="relative bg-card border rounded-lg shadow-lg w-full max-w-sm p-6 space-y-4">
          <div className="flex items-center justify-between">
            <h3 className="font-semibold">{t("frontend.dashboard.client.access_info")}</h3>
            <button
              type="button"
              className="inline-flex size-6 items-center justify-center rounded-md text-muted-foreground hover:text-foreground"
              onClick={() => onOpenChange(false)}
            >
              ×
            </button>
          </div>
          <div className="space-y-3">
            <div>
              <p className="text-xs text-muted-foreground mb-1">{t("frontend.profile.email")}</p>
              <p className="font-mono text-sm bg-muted p-2 rounded">{email}</p>
            </div>
            <div>
              <p className="text-xs text-muted-foreground mb-1">{t("frontend.subscriptions.password")}</p>
              <p className="font-mono text-sm bg-muted p-2 rounded">
                {password || "—"}
              </p>
            </div>
            {pin && (
              <div>
                <p className="text-xs text-muted-foreground mb-1">{t("frontend.subscriptions.pin")}</p>
                <p className="font-mono text-sm bg-muted p-2 rounded">{pin}</p>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
