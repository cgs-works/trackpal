import { Badge } from "@/components/ui/badge";
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

interface ExecutorTableProps {
  executors: LookupExecutor[];
}

export function ExecutorTable({ executors }: ExecutorTableProps) {
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
            </TableRow>
          </TableHeader>
          <TableBody>
            {executors.map((executor) => (
              <ExecutorRow key={executor.id} executor={executor} />
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
          </div>
        ))}
      </div>
    </>
  );
}

function ExecutorRow({ executor }: { executor: LookupExecutor }) {
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
    </TableRow>
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
  const translated = t(key, {
    active: executor.active_jobs,
    maximum: executor.max_concurrency,
  });
  const value = translated.startsWith(key)
    ? `${executor.active_jobs}/${executor.max_concurrency}`
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
    <Badge variant={status === "active" ? "default" : status === "disabled" ? "destructive" : "secondary"}>
      {t(`frontend.master.executors.status_${status}`)}
    </Badge>
  );
}

function HealthBadge({ status }: { status: LookupExecutorHealthStatus }) {
  return (
    <Badge variant={status === "healthy" ? "default" : status === "unhealthy" ? "destructive" : "secondary"}>
      {t(`frontend.master.executors.status_${status}`)}
    </Badge>
  );
}

function TransportBadge({ mode }: { mode: LookupExecutor["transport_mode"] }) {
  if (mode === "http_encrypted") {
    const key = "frontend.master.executors.transport_http_encrypted";
    const translated = t(key);
    return (
      <Badge variant="destructive" title={t("frontend.master.executors.transport_warning")}>
        {translated === key ? "HTTP encrypted" : translated}
      </Badge>
    );
  }
  const key = "frontend.master.executors.transport_https";
  const translated = t(key);
  return <Badge variant="secondary">{translated === key ? "HTTPS" : translated}</Badge>;
}

function ReverificationBadge() {
  return (
    <Badge variant="destructive">
      {t("frontend.master.executors.reverification_required")}
    </Badge>
  );
}

function formatDate(value: string): string {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return t("frontend.master.executors.not_available");
  return new Intl.DateTimeFormat(getLocale(), { dateStyle: "medium" }).format(date);
}
