import { useCallback, useEffect, useMemo, useState, type FormEvent } from "react";
import { Plus, RefreshCw, Search } from "lucide-react";
import { toast } from "sonner";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import { getApiError } from "@/lib/api-errors";
import { t } from "@/i18n";
import type { TenantPlan } from "@/features/auth/services/auth-api";
import {
  createDemo,
  deleteDemo,
  fetchDemos,
  replaceDemoCredentials,
  type DemoTenant,
  type DemoTenantCredentials,
} from "../services/demo-api";
import { DemoCredentialsDialog } from "./demo-credentials-dialog";
import { DemoFormDialog, type DemoForm } from "./demo-form-dialog";
import { DemoTable } from "./demo-table";

const EMPTY_FORM: DemoForm = { name: "", plan: "starter", locale: "en" };

export function DemosTab() {
  const [demos, setDemos] = useState<DemoTenant[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [searchQuery, setSearchQuery] = useState("");
  const [formOpen, setFormOpen] = useState(false);
  const [form, setForm] = useState<DemoForm>(EMPTY_FORM);
  const [formError, setFormError] = useState("");
  const [saving, setSaving] = useState(false);
  const [credentials, setCredentials] = useState<DemoTenantCredentials | null>(null);
  const [deleteTarget, setDeleteTarget] = useState<DemoTenant | null>(null);
  const [busyId, setBusyId] = useState<string | null>(null);

  const loadDemos = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      setDemos(await fetchDemos());
    } catch (loadError) {
      setError(getApiError(loadError, t("frontend.master.demos.error_load")));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void loadDemos();
  }, [loadDemos]);

  const filteredDemos = useMemo(() => {
    const query = searchQuery.trim().toLowerCase();
    if (!query) return demos;
    return demos.filter((demo) =>
      [demo.name, demo.username, demo.status, demo.plan].some((value) =>
        value.toLowerCase().includes(query),
      ),
    );
  }, [demos, searchQuery]);

  function openCreate() {
    setForm(EMPTY_FORM);
    setFormError("");
    setFormOpen(true);
  }

  function updateForm(key: keyof DemoForm, value: string) {
    setForm((current) => ({ ...current, [key]: value } as DemoForm));
  }

  async function handleCreate(event: FormEvent) {
    event.preventDefault();
    setFormError("");
    if (!form.name.trim()) {
      setFormError(t("frontend.master.demos.name_required"));
      return;
    }

    setSaving(true);
    try {
      const result = await createDemo({
        name: form.name.trim(),
        plan: form.plan as TenantPlan,
        locale: form.locale,
      });
      setFormOpen(false);
      setCredentials(result);
      await loadDemos();
    } catch (createError) {
      setFormError(getApiError(createError, t("frontend.master.demos.error_create")));
    } finally {
      setSaving(false);
    }
  }

  async function handleReplace(demo: DemoTenant) {
    if (demo.status === "expired") return;
    setBusyId(demo.id);
    try {
      const result = await replaceDemoCredentials(demo.id);
      setCredentials(result);
      await loadDemos();
    } catch (replaceError) {
      toast.error(
        getApiError(replaceError, t("frontend.master.demos.error_replace")),
      );
    } finally {
      setBusyId(null);
    }
  }

  async function handleDelete() {
    if (!deleteTarget) return;
    const target = deleteTarget;
    setBusyId(target.id);
    try {
      await deleteDemo(target.id);
      setDeleteTarget(null);
      toast.success(t("frontend.master.demos.delete_success"));
      await loadDemos();
    } catch (deleteError) {
      toast.error(
        getApiError(deleteError, t("frontend.master.demos.error_delete")),
      );
    } finally {
      setBusyId(null);
    }
  }

  function renderDemos() {
    if (loading) {
      return (
        <div className="flex flex-col gap-3 p-4" role="status">
          <span className="sr-only">{t("frontend.master.demos.loading")}</span>
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
            onClick={() => void loadDemos()}
          >
            {t("frontend.master.demos.retry")}
          </Button>
        </div>
      );
    }
    if (filteredDemos.length === 0) {
      return (
        <div className="flex flex-col items-center justify-center gap-3 p-10 text-center">
          <p className="text-sm text-muted-foreground">
            {searchQuery
              ? t("frontend.master.demos.empty_search")
              : t("frontend.master.demos.empty")}
          </p>
          {!searchQuery && (
            <Button type="button" size="sm" onClick={openCreate}>
              <Plus className="size-4" aria-hidden="true" />
              {t("frontend.master.demos.create_first")}
            </Button>
          )}
        </div>
      );
    }
    return (
      <DemoTable
        demos={filteredDemos}
        onReplace={(demo) => void handleReplace(demo)}
        onDelete={setDeleteTarget}
        busyId={busyId}
      />
    );
  }

  return (
    <div className="flex flex-col gap-6">
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h2 className="text-xl font-semibold">{t("frontend.master.demos.title")}</h2>
          <p className="text-sm text-muted-foreground">
            {t("frontend.master.demos.description")}
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Button
            type="button"
            variant="outline"
            size="sm"
            onClick={() => void loadDemos()}
            disabled={loading}
            aria-label={t("frontend.master.demos.refresh")}
          >
            <RefreshCw className="size-4" aria-hidden="true" />
            <span className="hidden sm:inline">{t("frontend.master.demos.refresh")}</span>
          </Button>
          <Button type="button" size="sm" onClick={openCreate}>
            <Plus className="size-4" aria-hidden="true" />
            {t("frontend.master.demos.create")}
          </Button>
        </div>
      </div>

      <div className="relative max-w-sm">
        <Search className="absolute left-3 top-1/2 size-4 -translate-y-1/2 text-muted-foreground" />
        <Input
          type="search"
          aria-label={t("frontend.master.demos.search_label")}
          placeholder={t("frontend.master.demos.search_placeholder")}
          value={searchQuery}
          onChange={(event) => setSearchQuery(event.target.value)}
          maxLength={120}
          className="pl-9"
        />
      </div>

      <div className="min-h-40 rounded-lg border">{renderDemos()}</div>

      <DemoFormDialog
        open={formOpen}
        form={form}
        saving={saving}
        error={formError}
        onOpenChange={setFormOpen}
        onFormChange={updateForm}
        onSubmit={handleCreate}
      />

      <DemoCredentialsDialog
        credentials={credentials}
        onDismiss={() => setCredentials(null)}
      />

      {deleteTarget && (
        <DemoDeleteDialog
          demo={deleteTarget}
          open
          onOpenChange={(open) => {
            if (!open) setDeleteTarget(null);
          }}
          onConfirm={() => void handleDelete()}
          deleting={busyId === deleteTarget.id}
        />
      )}
    </div>
  );
}

function DemoDeleteDialog({
  demo,
  open,
  deleting,
  onOpenChange,
  onConfirm,
}: {
  demo: DemoTenant;
  open: boolean;
  deleting: boolean;
  onOpenChange: (open: boolean) => void;
  onConfirm: () => void;
}) {
  return (
    <AlertDialog open={open} onOpenChange={onOpenChange}>
      <AlertDialogContent>
        <AlertDialogHeader>
          <AlertDialogTitle>{t("frontend.master.demos.delete_title")}</AlertDialogTitle>
          <AlertDialogDescription>
            {t("frontend.master.demos.delete_description", { name: demo.name })}
          </AlertDialogDescription>
        </AlertDialogHeader>
        <AlertDialogFooter>
          <AlertDialogCancel disabled={deleting}>
            {t("frontend.master.demos.cancel")}
          </AlertDialogCancel>
          <AlertDialogAction
            onClick={onConfirm}
            disabled={deleting}
            className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
          >
            {deleting
              ? t("frontend.master.demos.deleting")
              : t("frontend.master.demos.confirm_delete")}
          </AlertDialogAction>
        </AlertDialogFooter>
      </AlertDialogContent>
    </AlertDialog>
  );
}
