import { useState, useEffect, useCallback } from "react";
import { useNavigate } from "@tanstack/react-router";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Users, Plus, Search } from "lucide-react";
import { toast } from "sonner";
import { t } from "@/i18n";
import {
  listClients,
  createClient,
  updateClient,
  deactivateClient,
  activateClient,
  deleteClient,
  type Client,
} from "../services/client-api";
import { ClientTable } from "./client-table";
import {
  ClientFormDialog,
  getEmptyForm,
  type ClientForm,
} from "./client-form-dialog";
import { DeleteConfirmDialog } from "./client-delete-dialog";

export function ClientsPage() {
  const navigate = useNavigate();

  const [clients, setClients] = useState<Client[]>([]);
  const [filteredClients, setFilteredClients] = useState<Client[]>([]);
  const [search, setSearch] = useState("");
  const [isLoading, setIsLoading] = useState(true);
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

  // ── Load clients ────────────────────────────────────────────
  const loadClients = useCallback(async () => {
    setIsLoading(true);
    setError("");
    try {
      const data = await listClients();
      setClients(data);
      setFilteredClients(data);
    } catch (err) {
      setError(
        err instanceof Error ? err.message : t("frontend.clients.error_load")
      );
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    loadClients();
  }, [loadClients]);

  // ── Search filter ───────────────────────────────────────────
  useEffect(() => {
    if (!search) {
      setFilteredClients(clients);
      return;
    }
    const q = search.toLowerCase();
    setFilteredClients(
      clients.filter(
        (c) =>
          c.full_name.toLowerCase().includes(q) ||
          c.username.toLowerCase().includes(q) ||
          c.phone?.toLowerCase().includes(q)
      )
    );
  }, [search, clients]);

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
      local_username: client.username,
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
        await createClient({
          full_name: form.full_name,
          local_username: form.local_username,
          phone: form.phone || undefined,
          password: form.password,
        });
        toast.success(t("frontend.clients.created"));
      } else {
        await updateClient(form.id!, {
          full_name: form.full_name,
          local_username: form.local_username,
          phone: form.phone || undefined,
        });
        toast.success(t("frontend.clients.updated"));
      }
      setFormOpen(false);
      await loadClients();
    } catch (err) {
      const detail =
        err instanceof Error
          ? err.message
          : t("frontend.clients.error_save");
      setFormError(detail);
    } finally {
      setSaving(false);
    }
  }

  // ── Status toggle ───────────────────────────────────────────
  async function handleToggleStatus(client: Client) {
    try {
      if (client.is_active) {
        await deactivateClient(client.id);
        toast.success(t("frontend.clients.deactivated", { name: client.full_name }));
      } else {
        await activateClient(client.id);
        toast.success(t("frontend.clients.activated", { name: client.full_name }));
      }
      await loadClients();
    } catch (err) {
      toast.error(
        err instanceof Error ? err.message : t("frontend.clients.error_toggle_status")
      );
    }
  }

  // ── Delete ──────────────────────────────────────────────────
  function openDelete(client: Client) {
    setDeleteTarget(client);
    setDeleteOpen(true);
  }

  async function handleDelete() {
    if (!deleteTarget) return;
    try {
      await deleteClient(deleteTarget.id);
      toast.success(t("frontend.clients.deleted", { name: deleteTarget.full_name }));
      setDeleteOpen(false);
      setDeleteTarget(null);
      await loadClients();
    } catch (err) {
      toast.error(
        err instanceof Error ? err.message : t("frontend.clients.error_delete")
      );
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
    <div className="flex-1 p-6">
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

        {/* Search */}
        <div className="relative max-w-sm">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 size-4 text-muted-foreground" />
          <Input
            placeholder={t("frontend.clients.search_placeholder")}
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="pl-9"
          />
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
            <h3 className="text-lg font-medium">
              {t("frontend.clients.no_clients")}
            </h3>
            <p className="text-muted-foreground mt-1">
              {search
                ? t("frontend.clients.search_no_results")
                : t("frontend.clients.create_first")}
            </p>
            {!search && (
              <Button onClick={openCreate} className="mt-4">
                <Plus className="size-4 mr-2" />
                {t("frontend.clients.create")}
              </Button>
            )}
          </div>
        ) : (
          <>
            <div className="text-sm text-muted-foreground">
              {filteredClients.length} client
              {filteredClients.length !== 1 ? "s" : ""}
            </div>
            <ClientTable
              clients={filteredClients}
              onEdit={openEdit}
              onDelete={openDelete}
              onToggleStatus={handleToggleStatus}
              onViewSubscriptions={handleViewSubscriptions}
            />
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
        onConfirm={handleDelete}
      />
    </div>
  );
}
