import { useState, useEffect, useCallback } from "react";
import { useNavigate } from "@tanstack/react-router";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Users, Plus, Search } from "lucide-react";
import { toast } from "sonner";
import { t } from "@/i18n";
import { type Client } from "../services/client-api";
import type { DeletePreview } from "../services/catalog-api";
import { useCatalogStore } from "@/store/catalog";
import { useAuthStore } from "@/store/auth";
import { ClientTable } from "./client-table";
import {
  ClientFormDialog,
  getEmptyForm,
  type ClientForm,
} from "./client-form-dialog";
import { DeleteConfirmDialog } from "./client-delete-dialog";

const CLIENT_ERROR_KEYS: Record<string, string> = {
  client_local_username_exists: "frontend.clients.error_username_exists",
  phone_already_registered: "frontend.clients.error_phone_exists",
  client_delete_active: "frontend.clients.cannot_delete_active",
  client_has_subscriptions: "frontend.clients.error_has_subscriptions",
  client_validation_failed: "frontend.clients.error_validation",
};

function getClientErrorMessage(error: unknown, fallback: string): string {
  let code: string | undefined;
  let detail: unknown;
  if (error && typeof error === "object") {
    if ("code" in error && typeof error.code === "string") code = error.code;
    if ("response" in error && error.response && typeof error.response === "object" && "data" in error.response) {
      const data = error.response.data;
      if (data && typeof data === "object" && "detail" in data) detail = data.detail;
    }
  }
  if (code && CLIENT_ERROR_KEYS[code]) return t(CLIENT_ERROR_KEYS[code]);
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail) && detail.length > 0) {
    return detail.map((item) => {
      if (item && typeof item === "object" && "msg" in item && typeof item.msg === "string") return item.msg;
      return t("frontend.clients.error_validation");
    }).join("; ");
  }
  return error instanceof Error ? error.message : fallback;
}

export function ClientsPage() {
  const navigate = useNavigate();

  const { dataSource } = useAuthStore();
  const { clients, loadClients, invalidateClients } = useCatalogStore();
  const [filteredClients, setFilteredClients] = useState<Client[]>([]);
  const [search, setSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState<"all" | "active" | "inactive">("all");
  const [page, setPage] = useState(1);
  const [isLoading, setIsLoading] = useState(!useCatalogStore.getState().clientsLoaded);
  const [error, setError] = useState("");

  // Form state
  const [formOpen, setFormOpen] = useState(false);
  const [formMode, setFormMode] = useState<"create" | "edit">("create");
  const [form, setForm] = useState<ClientForm>(getEmptyForm());
  const [saving, setSaving] = useState(false);
  const [formError, setFormError] = useState("");

  // Delete state
  const [deleteOpen, setDeleteOpen] = useState(false);
  const [deleteTarget, setDeleteTarget] = useState<Client | null>(null);
  const [deletePreview, setDeletePreview] = useState<DeletePreview | null>(null);
  const [deletePreviewLoading, setDeletePreviewLoading] = useState(false);
  const [deletePreviewError, setDeletePreviewError] = useState("");

  // ── Load clients ────────────────────────────────────────────
  const loadClientsData = useCallback(async () => {
    setIsLoading(true);
    setError("");
    try {
      await loadClients(dataSource.crud.clients);
    } catch (err) {
      setError(getClientErrorMessage(err, t("frontend.clients.error_load")));
    } finally {
      setIsLoading(false);
    }
  }, [dataSource, loadClients]);

  useEffect(() => {
    loadClientsData();
  }, [loadClientsData]);

  // ── Search and status filter ────────────────────────────────
  useEffect(() => {
    const q = search.toLowerCase();
    setFilteredClients(
      clients.filter((client) => {
        const matchesSearch =
          !q ||
          client.full_name.toLowerCase().includes(q) ||
          client.username.toLowerCase().includes(q) ||
          client.phone?.toLowerCase().includes(q);
        const matchesStatus =
          statusFilter === "all" ||
          (statusFilter === "active" && client.is_active) ||
          (statusFilter === "inactive" && !client.is_active);
        return matchesSearch && matchesStatus;
      }),
    );
    setPage(1);
  }, [search, statusFilter, clients]);

  const pageSize = 10;
  const totalPages = Math.max(1, Math.ceil(filteredClients.length / pageSize));
  const visibleClients = filteredClients.slice((page - 1) * pageSize, page * pageSize);

  // ── Form handlers ───────────────────────────────────────────
  function handleFormChange(key: keyof ClientForm, value: string) {
    setForm((prev) => ({ ...prev, [key]: value }));
  }

  function openCreate() {
    setFormMode("create");
    setForm(getEmptyForm());
    setFormError("");
    setFormOpen(true);
  }

  function openEdit(client: Client) {
    setFormMode("edit");
    setForm({
      id: client.id,
      full_name: client.full_name,
      local_username:
        dataSource.mode === "demo" && client.username.startsWith("demo_")
          ? client.username.slice("demo_".length)
          : client.username,
      phone: client.phone || "",
      password: "",
    });
    setFormError("");
    setFormOpen(true);
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setSaving(true);
    setFormError("");

    try {
      if (formMode === "create") {
        const created = await dataSource.crud.clients.create({
          full_name: form.full_name,
          local_username: form.local_username,
          phone: form.phone || undefined,
          password: form.password,
        });
        toast.success(t("frontend.clients.created", { login: created.username }));
      } else {
        const updated = await dataSource.crud.clients.update(form.id!, {
          full_name: form.full_name,
          local_username: form.local_username,
          phone: form.phone || undefined,
        });
        toast.success(t("frontend.clients.updated", { login: updated.username }));
      }
      setFormOpen(false);
      invalidateClients();
      await loadClientsData();
    } catch (err: unknown) {
      setFormError(getClientErrorMessage(err, t("frontend.clients.error_save")));
    } finally {
      setSaving(false);
    }
  }

  // ── Status toggle ───────────────────────────────────────────
  async function handleToggleStatus(client: Client) {
    try {
      if (client.is_active) {
        await dataSource.crud.clients.deactivate(client.id);
        toast.success(t("frontend.clients.deactivated", { name: client.full_name }));
      } else {
        await dataSource.crud.clients.activate(client.id);
        toast.success(t("frontend.clients.activated", { name: client.full_name }));
      }
      invalidateClients();
      await loadClientsData();
    } catch (err) {
      toast.error(getClientErrorMessage(err, t("frontend.clients.error_toggle_status")));
    }
  }

  // ── Delete ──────────────────────────────────────────────────
  async function openDelete(client: Client) {
    setDeleteTarget(client);
    setDeletePreview(null);
    setDeletePreviewError("");
    setDeletePreviewLoading(true);
    setDeleteOpen(true);
    try {
      setDeletePreview(await dataSource.crud.clients.getDeletePreview(client.id));
    } catch (error) {
      setDeletePreviewError(getClientErrorMessage(error, t("frontend.clients.error_delete")));
    } finally {
      setDeletePreviewLoading(false);
    }
  }

  async function handleDelete() {
    if (!deleteTarget) return;
    try {
      await dataSource.crud.clients.delete(deleteTarget.id);
      toast.success(t("frontend.clients.deleted", { name: deleteTarget.full_name }));
      setDeleteOpen(false);
      setDeleteTarget(null);
      invalidateClients();
      await loadClientsData();
    } catch (err) {
      toast.error(getClientErrorMessage(err, t("frontend.clients.error_delete")));
    }
  }

  // ── View subscriptions ──────────────────────────────────────
  function handleViewSubscriptions(client: Client) {
    navigate({
      to: "/admin/subscriptions",
      search: { client_id: client.id },
    });
  }

  return (
    <div className="flex-1 p-6" data-help-id="admin.clients">
      <div className="max-w-5xl mx-auto space-y-6">
        {/* Header */}
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-bold tracking-tight">{t("frontend.clients.section_title")}</h1>
            <p className="text-muted-foreground">
              {t("frontend.clients.section_heading")}
            </p>
          </div>
          <Button onClick={openCreate}>
            <Plus className="size-4 mr-2" />
            {t("frontend.clients.create")}
          </Button>
        </div>

        {/* Search and status filter */}
        <div className="flex flex-wrap items-center gap-3">
          <div className="relative max-w-sm flex-1">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 size-4 text-muted-foreground" />
            <Input
              placeholder={t("frontend.clients.search_placeholder")}
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              className="pl-9"
            />
          </div>
          <label htmlFor="client-status-filter" className="sr-only">
            {t("frontend.clients.status_filter")}
          </label>
          <select
            id="client-status-filter"
            aria-label={t("frontend.clients.status_filter")}
            value={statusFilter}
            onChange={(event) => setStatusFilter(event.target.value as typeof statusFilter)}
            className="h-10 rounded-md border border-input bg-background px-3 text-sm"
          >
            <option value="all">{t("frontend.clients.status_all")}</option>
            <option value="active">{t("frontend.clients.status_active")}</option>
            <option value="inactive">{t("frontend.clients.status_inactive")}</option>
          </select>
        </div>

        {/* Error */}
        {error && (
          <div className="rounded-lg bg-destructive/10 border border-destructive/20 p-3 text-sm text-destructive">
            {error}
          </div>
        )}

        {/* Content */}
        {isLoading ? (
          <div className="flex items-center justify-center py-12 text-muted-foreground">
            <div className="flex items-center gap-3">
              <div className="size-5 border-2 border-border border-t-primary rounded-full animate-spin" />
              {t("frontend.clients.loading")}
            </div>
          </div>
        ) : filteredClients.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-12 text-center">
            <Users className="size-12 text-muted-foreground/50 mb-4" />
            <h3 className="text-lg font-medium">{t("frontend.clients.no_clients")}</h3>
            <p className="text-muted-foreground mt-1">
              {search || statusFilter !== "all"
                ? t("frontend.clients.search_no_results")
                : t("frontend.clients.create_first")}
            </p>
            {!search && statusFilter === "all" && (
              <Button onClick={openCreate} className="mt-4">
                <Plus className="size-4 mr-2" />
                {t("frontend.clients.create")}
              </Button>
            )}
          </div>
        ) : (
          <>
            <div className="text-sm text-muted-foreground">
              {filteredClients.length} {t("frontend.clients.count_label")}
            </div>
            <ClientTable
              clients={visibleClients}
              onEdit={openEdit}
              onDelete={openDelete}
              onToggleStatus={handleToggleStatus}
              onViewSubscriptions={handleViewSubscriptions}
            />
            {totalPages > 1 && (
              <div className="flex items-center justify-between gap-3" aria-label={t("frontend.clients.pagination")}>
                <span className="text-sm text-muted-foreground">
                  {t("frontend.clients.page", { page, total: totalPages })}
                </span>
                <div className="flex gap-2">
                  <Button
                    variant="outline"
                    size="sm"
                    disabled={page === 1}
                    onClick={() => setPage((current) => Math.max(1, current - 1))}
                  >
                    {t("frontend.clients.previous")}
                  </Button>
                  <Button
                    variant="outline"
                    size="sm"
                    disabled={page === totalPages}
                    onClick={() => setPage((current) => Math.min(totalPages, current + 1))}
                  >
                    {t("frontend.clients.next")}
                  </Button>
                </div>
              </div>
            )}
          </>
        )}
      </div>

      {/* Form dialog */}
      <ClientFormDialog
        open={formOpen}
        onOpenChange={setFormOpen}
        mode={formMode}
        form={form}
        onFormChange={handleFormChange}
        onSubmit={handleSubmit}
        saving={saving}
        error={formError}
      />

      {/* Delete dialog */}
      <DeleteConfirmDialog
        open={deleteOpen}
        onOpenChange={setDeleteOpen}
        clientName={deleteTarget?.full_name || ""}
        preview={deletePreview}
        loading={deletePreviewLoading}
        error={deletePreviewError}
        onConfirm={handleDelete}
      />
    </div>
  );
}
