import { KeyRound, Trash2 } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Table,
  TableBody,
  TableCell,
  TableCaption,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Separator } from "@/components/ui/separator";
import { getLocale, t } from "@/i18n";
import type { DemoTenant, DemoTenantStatus } from "../services/demo-api";

interface DemoTableProps {
  demos: DemoTenant[];
  onReplace: (demo: DemoTenant) => void;
  onDelete: (demo: DemoTenant) => void;
  busyId: string | null;
}

export function DemoTable({ demos, onReplace, onDelete, busyId }: DemoTableProps) {
  return (
    <>
      <div className="hidden overflow-x-auto md:block" data-testid="demo-desktop-table">
        <Table>
          <TableCaption className="sr-only">{t("frontend.master.demos.title")}</TableCaption>
          <TableHeader>
            <TableRow>
              <TableHead>{t("frontend.master.demos.name_column")}</TableHead>
              <TableHead>{t("frontend.master.demos.plan_column")}</TableHead>
              <TableHead>{t("frontend.master.demos.username_column")}</TableHead>
              <TableHead>{t("frontend.master.demos.status_column")}</TableHead>
              <TableHead>{t("frontend.master.demos.lifecycle_column")}</TableHead>
              <TableHead className="text-right">{t("frontend.master.demos.actions_column")}</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {demos.map((demo) => (
              <DemoRow
                key={demo.id}
                demo={demo}
                busy={busyId === demo.id}
                onReplace={onReplace}
                onDelete={onDelete}
              />
            ))}
          </TableBody>
        </Table>
      </div>

      <div className="divide-y md:hidden" data-testid="demo-mobile-list">
        {demos.map((demo) => (
          <div key={demo.id} className="flex flex-col gap-3 p-4">
            <div className="flex items-start justify-between gap-3">
              <div className="min-w-0">
                <p className="break-words font-medium" title={demo.name}>{demo.name}</p>
                <p className="break-all text-sm text-muted-foreground" title={demo.username}>{demo.username}</p>
              </div>
              <div className="flex shrink-0 items-center gap-2">
                <PlanBadge plan={demo.plan} />
                <StatusBadge status={demo.status} />
              </div>
            </div>
            <LifecycleDetails demo={demo} />
            <Separator />
            <DemoActions
              demo={demo}
              busy={busyId === demo.id}
              onReplace={onReplace}
              onDelete={onDelete}
            />
          </div>
        ))}
      </div>
    </>
  );
}

function DemoRow({
  demo,
  busy,
  onReplace,
  onDelete,
}: {
  demo: DemoTenant;
  busy: boolean;
  onReplace: (demo: DemoTenant) => void;
  onDelete: (demo: DemoTenant) => void;
}) {
  return (
    <TableRow>
      <TableCell className="max-w-56 whitespace-normal break-words font-medium">{demo.name}</TableCell>
      <TableCell><PlanBadge plan={demo.plan} /></TableCell>
      <TableCell className="max-w-48 whitespace-normal break-all"><code>{demo.username}</code></TableCell>
      <TableCell><StatusBadge status={demo.status} /></TableCell>
      <TableCell><LifecycleDetails demo={demo} /></TableCell>
      <TableCell className="text-right">
        <DemoActions demo={demo} busy={busy} onReplace={onReplace} onDelete={onDelete} />
      </TableCell>
    </TableRow>
  );
}

function DemoActions({
  demo,
  busy,
  onReplace,
  onDelete,
}: {
  demo: DemoTenant;
  busy: boolean;
  onReplace: (demo: DemoTenant) => void;
  onDelete: (demo: DemoTenant) => void;
}) {
  const replaceLabel = t("frontend.master.demos.replace_credentials", {
    name: demo.name,
  });
  const deleteLabel = t("frontend.master.demos.delete_demo", { name: demo.name });
  return (
    <div className="flex flex-wrap items-center justify-end gap-1">
      <Button
        type="button"
        variant="ghost"
        size="sm"
        onClick={() => onReplace(demo)}
        disabled={busy || demo.status === "expired"}
        aria-label={replaceLabel}
        title={replaceLabel}
      >
        <KeyRound className="size-3.5" />
        <span className="sm:inline">{t("frontend.master.demos.replace")}</span>
      </Button>
      <Button
        type="button"
        variant="ghost"
        size="sm"
        className="text-destructive hover:text-destructive"
        onClick={() => onDelete(demo)}
        disabled={busy}
        aria-label={deleteLabel}
        title={deleteLabel}
      >
        <Trash2 className="size-3.5" />
        <span className="sm:inline">{t("frontend.master.demos.delete")}</span>
      </Button>
    </div>
  );
}

function PlanBadge({ plan }: { plan: DemoTenant["plan"] }) {
  return (
    <Badge variant={plan === "pro" ? "default" : "secondary"}>
      {plan === "pro"
        ? t("frontend.master.demos.pro")
        : t("frontend.master.demos.starter")}
    </Badge>
  );
}

function StatusBadge({ status }: { status: DemoTenantStatus }) {
  const styles: Record<DemoTenantStatus, string> = {
    pending: "border-border bg-muted text-foreground",
    active: "border-primary/30 bg-primary/10 text-foreground",
    expired: "border-destructive/30 bg-destructive/10 text-destructive",
  };

  return (
    <Badge variant="secondary" className={styles[status]}>
      {t(`frontend.master.demos.status_${status}`)}
    </Badge>
  );
}

function LifecycleDetails({ demo }: { demo: DemoTenant }) {
  const created = formatDate(demo.created_at);
  const activated = demo.demo_activated_at
    ? formatDate(demo.demo_activated_at)
    : t("frontend.master.demos.not_available");

  if (demo.status === "pending") {
    return (
      <div className="text-sm">
        <div className="text-muted-foreground">
          {t("frontend.master.demos.pending_lifecycle")}
        </div>
        <div>{t("frontend.master.demos.created", { date: created })}</div>
      </div>
    );
  }

  const date = demo.demo_expires_at
    ? formatDate(demo.demo_expires_at)
    : t("frontend.master.demos.not_available");
  const remaining = demo.remaining_seconds === null
    ? null
    : formatRemaining(demo.remaining_seconds);

  return (
    <div className="text-sm">
      <div>{t("frontend.master.demos.started", { date: activated })}</div>
      <div>
        {demo.status === "active"
          ? t("frontend.master.demos.expires", { date })
          : t("frontend.master.demos.expired_on", { date })}
      </div>
      {remaining && (
        <div className="text-muted-foreground">
          {t("frontend.master.demos.remaining", { value: remaining })}
        </div>
      )}
    </div>
  );
}

function formatDate(value: string): string {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return t("frontend.master.demos.not_available");
  return new Intl.DateTimeFormat(getLocale(), {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(date);
}

function formatRemaining(seconds: number): string {
  const safeSeconds = Number.isFinite(seconds) ? Math.max(0, seconds) : 0;
  const hours = Math.floor(safeSeconds / 3600);
  if (hours > 0) return t("frontend.master.demos.hours", { hours });
  return t("frontend.master.demos.minutes", {
    minutes: Math.max(1, Math.floor(safeSeconds / 60)),
  });
}
