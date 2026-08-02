import { useCallback, useEffect, useState } from "react";
import { RefreshCw } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { t } from "@/i18n";
import { mapExecutorError, fetchLookupExecutors, type LookupExecutor } from "../services/executor-api";
import { ExecutorTable } from "./executor-table";

export function LookupExecutorsPage() {
  const [executors, setExecutors] = useState<LookupExecutor[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const loadExecutors = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      setExecutors(await fetchLookupExecutors());
    } catch (loadError) {
      setError(
        mapExecutorError(loadError, "frontend.master.executors.error_load"),
      );
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void loadExecutors();
  }, [loadExecutors]);

  function renderContent() {
    if (loading) {
      return (
        <div className="flex flex-col gap-3 p-4" role="status">
          <span className="sr-only">{t("frontend.master.executors.loading")}</span>
          {Array.from({ length: 3 }).map((_, index) => (
            <Skeleton key={index} className="h-12 w-full rounded-lg" />
          ))}
        </div>
      );
    }

    if (error) {
      return (
        <div className="flex flex-col items-center justify-center gap-3 p-10 text-center">
          <p role="alert" className="text-sm text-destructive">{error}</p>
          <Button
            type="button"
            variant="outline"
            size="sm"
            onClick={() => void loadExecutors()}
          >
            {t("frontend.master.executors.retry")}
          </Button>
        </div>
      );
    }

    if (executors.length === 0) {
      return (
        <div className="flex flex-col items-center justify-center gap-3 p-10 text-center">
          <p className="text-sm text-muted-foreground">
            {t("frontend.master.executors.empty")}
          </p>
        </div>
      );
    }

    return <ExecutorTable executors={executors} />;
  }

  return (
    <div className="flex-1 overflow-auto">
      <div className="mx-auto flex max-w-7xl flex-col gap-6 px-4 py-6 sm:px-6">
        <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <h1 className="text-xl font-semibold">{t("frontend.master.executors.title")}</h1>
            <p className="text-sm text-muted-foreground">
              {t("frontend.master.executors.description")}
            </p>
          </div>
          <Button
            type="button"
            variant="outline"
            size="sm"
            onClick={() => void loadExecutors()}
            disabled={loading}
            aria-label={t("frontend.master.executors.refresh")}
          >
            <RefreshCw data-icon="inline-start" aria-hidden="true" />
            <span className="hidden sm:inline">{t("frontend.master.executors.refresh")}</span>
          </Button>
        </div>

        <div className="min-h-40 rounded-lg border">{renderContent()}</div>
      </div>
    </div>
  );
}
