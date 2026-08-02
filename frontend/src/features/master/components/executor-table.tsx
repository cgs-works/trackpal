import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Check,
  Eye,
  FlaskConical,
  Play,
  RotateCw,
  ShieldOff,
  Trash2,
} from "lucide-react";
import {
  Table,
  TableBody,
  TableCaption,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Separator } from "@/components/ui/separator";
import { getLocale, t } from "@/i18n";
import type {
  LookupExecutor,
  LookupExecutorHealthStatus,
  LookupExecutorLifecycleStatus,
} from "../services/executor-api";
import type { ExecutorAction } from "./executor-action-dialogs";

interface ExecutorTableProps {
  executors: LookupExecutor[];
  onAction: (action: ExecutorAction, executor: LookupExecutor) => void;
}

export function ExecutorTable({ executors, onAction }: ExecutorTableProps) {
  return (
    <>
      <div className="hidden overflow-x-auto md:block" data-testid="executor-desktop-table">
        <Table>
          <TableCaption className="sr-only">{t("frontend.master.executors.list")}</TableCaption>
          <TableHeader>
            <TableRow>
              <TableHead>{t("frontend.master.executors.name")}</TableHead>
              <TableHead>{t("frontend.master.executors.provider")}</TableHead>
              <TableHead>{t("frontend.master.executors.status")}</TableHead>
              <TableHead>{t("frontend.master.executors.health")}</TableHead>
              <TableHead>{t("frontend.master.executors.capacity")}</TableHead>
              <TableHead>{t("frontend.master.executors.transport_mode")}</TableHead>
              <TableHead>{t("frontend.master.executors.last_error")}</TableHead>
              <TableHead>{t("frontend.master.executors.actions")}</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {executors.map((executor) => (
              <ExecutorRow key={executor.id} executor={executor} onAction={onAction} />
            ))}
          </TableBody>
        </Table>
      </div>

      <div className="divide-y md:hidden" data-testid="executor-mobile-list">
        {executors.map((executor) => (
          <div key={executor.id} className="flex flex-col gap-3 p-4">
            <div className="flex items-start justify-between gap-3">
              <div className="min-w-0">
                <p className="break-words font-medium">{executor.name}</p>
                <p className="break-words text-sm text-muted-foreground">{executor.provider_label}</p>
              </div>
              <LifecycleBadge status={executor.lifecycle_status} />
            </div>
            <div className="flex flex-wrap items-center gap-2">
              <HealthBadge status={executor.health_status} />
              <CapacityBadge executor={executor} />
              <TransportBadge mode={executor.transport_mode} />
              {executor.requires_reverification && <ReverificationBadge />}
            </div>
            <OperationalDetails executor={executor} />
            <Separator />
            <ErrorDetails executor={executor} />
            <ExecutorActions executor={executor} onAction={onAction} />
          </div>
        ))}
      </div>
    </>
  );
}

function ExecutorRow({
  executor,
  onAction,
}: {
  executor: LookupExecutor;
  onAction: (action: ExecutorAction, executor: LookupExecutor) => void;
}) {
  return (
    <TableRow>
      <TableCell className="max-w-56 whitespace-normal break-words font-medium">
        {executor.name}
      </TableCell>
      <TableCell className="max-w-40 whitespace-normal break-words">
        {executor.provider_label}
      </TableCell>
      <TableCell><LifecycleBadge status={executor.lifecycle_status} /></TableCell>
      <TableCell><HealthBadge status={executor.health_status} /></TableCell>
      <TableCell><CapacityBadge executor={executor} /></TableCell>
      <TableCell><TransportBadge mode={executor.transport_mode} /></TableCell>
      <TableCell className="max-w-64 whitespace-normal break-words">
        <ErrorDetails executor={executor} />
        {executor.requires_reverification && <ReverificationBadge />}
      </TableCell>
      <TableCell>
        <ExecutorActions executor={executor} onAction={onAction} />
      </TableCell>
    </TableRow>
  );
}

function ExecutorActions({
  executor,
  onAction,
}: {
  executor: LookupExecutor;
  onAction: (action: ExecutorAction, executor: LookupExecutor) => void;
}) {
  const lifecycleAction: ExecutorAction = executor.lifecycle_status === "active" ? "disable" : "enable";
  return (
    <div className="flex flex-wrap gap-1">
      <ActionButton action="verify" icon={Check} executor={executor} onAction={onAction} />
      <ActionButton action="test" icon={FlaskConical} executor={executor} onAction={onAction} />
      <ActionButton action={lifecycleAction} icon={lifecycleAction === "enable" ? Play : ShieldOff} executor={executor} onAction={onAction} />
      <ActionButton action="rotate" icon={RotateCw} executor={executor} onAction={onAction} />
      {executor.has_hosting_password && (
        <ActionButton action="reveal" icon={Eye} executor={executor} onAction={onAction} />
      )}
      <ActionButton
        action="delete"
        icon={Trash2}
        executor={executor}
        onAction={onAction}
        disabled={executor.active_jobs > 0}
        variant="destructive"
      />
    </div>
  );
}

function ActionButton({
  action,
  icon: Icon,
  executor,
  onAction,
  disabled = false,
  variant = "outline",
}: {
  action: ExecutorAction;
  icon: typeof Check;
  executor: LookupExecutor;
  onAction: (action: ExecutorAction, executor: LookupExecutor) => void;
  disabled?: boolean;
  variant?: "outline" | "destructive";
}) {
  const label = t(`frontend.master.executors.${actionLabelKey[action]}`);
  return (
    <Button
      type="button"
      variant={variant}
      size="icon-sm"
      aria-label={label}
      title={label}
      disabled={disabled}
      onClick={() => onAction(action, executor)}
    >
      <Icon data-icon="inline-start" aria-hidden="true" />
    </Button>
  );
}

function OperationalDetails({ executor }: { executor: LookupExecutor }) {
  return (
    <div className="flex flex-wrap items-center gap-2 text-sm">
      <span className="text-muted-foreground">{formatDate(executor.updated_at)}</span>
    </div>
  );
}

function CapacityBadge({ executor }: { executor: LookupExecutor }) {
  const key = "frontend.master.executors.capacity_value";
  const activeLeases = executor.active_leases ?? "—";
  const translated = t(key, {
    active: activeLeases,
    maximum: executor.max_concurrency,
  });
  const value = translated.startsWith(key)
    ? `${activeLeases}/${executor.max_concurrency}`
    : translated;
  return <Badge variant="outline">{value}</Badge>;
}

function ErrorDetails({ executor }: { executor: LookupExecutor }) {
  return executor.last_error_safe ? (
    <span title={executor.last_error_safe}>{executor.last_error_safe}</span>
  ) : (
    <span className="text-muted-foreground">{t("frontend.master.executors.no_error")}</span>
  );
}

function LifecycleBadge({ status }: { status: LookupExecutorLifecycleStatus }) {
  return (
    <Badge variant={lifecycleBadgeVariant[status]}>
      {t(`frontend.master.executors.status_${status}`)}
    </Badge>
  );
}

function HealthBadge({ status }: { status: LookupExecutorHealthStatus }) {
  return (
    <Badge variant={healthBadgeVariant[status]}>
      {t(`frontend.master.executors.status_${status}`)}
    </Badge>
  );
}

function TransportBadge({ mode }: { mode: LookupExecutor["transport_mode"] }) {
  if (mode === "http_encrypted") {
    const key = "frontend.master.executors.transport_http_encrypted";
    return (
      <Badge variant="destructive" title={t("frontend.master.executors.transport_warning")}>
        {t(key)}
      </Badge>
    );
  }
  const key = "frontend.master.executors.transport_https";
  return <Badge variant="secondary">{t(key)}</Badge>;
}

function ReverificationBadge() {
  return (
    <Badge variant="destructive">
      {t("frontend.master.executors.reverification_required")}
    </Badge>
  );
}

const actionLabelKey: Record<ExecutorAction, string> = {
  verify: "verify",
  test: "test",
  enable: "enable",
  disable: "disable",
  rotate: "rotate_secret",
  reveal: "reveal_hosting_password",
  delete: "delete",
};

const lifecycleBadgeVariant: Record<
  LookupExecutorLifecycleStatus,
  "default" | "destructive" | "secondary"
> = {
  active: "default",
  disabled: "destructive",
  draft: "secondary",
};

const healthBadgeVariant: Record<
  LookupExecutorHealthStatus,
  "default" | "destructive" | "secondary"
> = {
  healthy: "default",
  unhealthy: "destructive",
  unknown: "secondary",
};

function formatDate(value: string): string {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return t("frontend.master.executors.not_available");
  return new Intl.DateTimeFormat(getLocale(), { dateStyle: "medium" }).format(date);
}
