import { useState, useEffect, useCallback } from "react";
import { useNavigate } from "@tanstack/react-router";
import { toast } from "sonner";
import { useAuthStore } from "@/store/auth";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import { SummaryCards } from "./summary-cards";
import { BusinessTable } from "./business-table";
import { BusinessFormDialog, getEmptyForm, type BusinessForm } from "./business-form-dialog";
import { DeleteConfirmDialog } from "./delete-confirm-dialog";
import { EmptyState } from "./empty-state";
import {
  fetchTenants,
  createTenant,
  updateTenant,
  deleteTenant,
  activateTenant,
  deactivateTenant,
  type Tenant,
  type TenantMeta,
} from "../services/tenant-api";
import { Plus, Search } from "lucide-react";

/* ── Helpers ────────────────────────────────────────────────────── */

function getApiError(error: unknown, fallback: string): string {
  const err = error as {
    response?: { data?: { detail?: string | Array<{ msg?: string }> } }
  }
  const detail = err.response?.data?.detail
  if (Array.isArray(detail)) {
    return detail.map((item) => item.msg || String(item)).join(", ")
  }
  return (typeof detail === "string" ? detail : null) || fallback
}

function getGeneratedPassword(data: unknown): string {
  const d = data as Record<string, unknown>
  return (
    (d?.generated_password as string) ||
    (d?.password as string) ||
    (d?.temporary_password as string) ||
    (d?.plain_password as string) ||
    ""
  )
}

/* ── Dashboard Page ─────────────────────────────────────────────── */

export function DashboardPage() {
  const navigate = useNavigate();
  const { switchTenant } = useAuthStore();

  const [tenants, setTenants] = useState<Tenant[]>([]);
  const [meta, setMeta] = useState<TenantMeta>({ total: 0, active: 0, inactive: 0 });
  const [isLoading, setIsLoading] = useState(false);
  const [searchQuery, setSearchQuery] = useState("");

  const [formOpen, setFormOpen] = useState(false);
  const [formMode, setFormMode] = useState<"create" | "edit">("create");
  const [form, setForm] = useState<BusinessForm>(getEmptyForm());
  const [isSaving, setIsSaving] = useState(false);
  const [formError, setFormError] = useState("");

  const [deleteTarget, setDeleteTarget] = useState<Tenant | null>(null);

  /* ── Data loading ─────────────────────────────────────────────── */

  const loadTenants = useCallback(async () => {
    setIsLoading(true);
    try {
      const res = await fetchTenants();
      setTenants(res.data || []);
      setMeta(
        res.meta || {
          total: (res.data || []).length,
          active: (res.data || []).filter((t) => t.is_active).length,
          inactive: (res.data || []).filter((t) => !t.is_active).length,
        }
      );
    } catch (error) {
      toast.error(getApiError(error, "Unable to load businesses"));
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    loadTenants();
  }, [loadTenants]);

  /* ── Filtered tenants ─────────────────────────────────────────── */

  const filteredTenants = tenants.filter((t) => {
    if (!searchQuery) return true;
    const q = searchQuery.toLowerCase();
    return (
      t.full_name.toLowerCase().includes(q) ||
      t.email?.toLowerCase().includes(q) ||
      t.client_prefix?.toLowerCase().includes(q)
    );
  });

  /* ── Form handlers ────────────────────────────────────────────── */

  function openCreate() {
    setFormMode("create");
    setForm(getEmptyForm());
    setFormOpen(true);
  }

  function openEdit(tenant: Tenant) {
    setFormMode("edit");
    setForm({
      ...getEmptyForm(),
      id: tenant.id,
      full_name: tenant.full_name || "",
      email: tenant.email || "",
      phone: tenant.phone || "",
      client_prefix: tenant.client_prefix || "",
      evolution_instance_name: tenant.evolution_instance_name || "",
    });
    setFormOpen(true);
  }

  function updateForm(key: keyof BusinessForm, value: string) {
    setForm((prev) => ({ ...prev, [key]: value }));
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setFormError("");

    if (!form.full_name || !form.email || !form.phone) {
      setFormError("Full name, email, and phone are required.");
      return;
    }
    if (formMode === "create" && !form.username) {
      setFormError("Username is required.");
      return;
    }
    if (!form.evolution_instance_name) {
      setFormError("Evolution instance name is required.");
      return;
    }

    setIsSaving(true);
    try {
      if (formMode === "edit") {
        const payload: Record<string, unknown> = {
          full_name: form.full_name,
          email: form.email,
          phone: form.phone,
          evolution_instance_name: form.evolution_instance_name,
        };
        if (form.client_prefix.trim()) payload.client_prefix = form.client_prefix;
        await updateTenant(form.id!, payload);
        toast.success("Business updated");
      } else {
        const payload: Record<string, unknown> = {
          full_name: form.full_name,
          email: form.email,
          phone: form.phone,
          username: form.username,
          evolution_instance_name: form.evolution_instance_name,
        };
        if (form.client_prefix.trim()) payload.client_prefix = form.client_prefix;
        if (form.password) payload.password = form.password;
        const res = await createTenant(payload);
        const pw = getGeneratedPassword(res);
        toast.success(pw ? `Business created. Password: ${pw}` : "Business created");
      }
      setFormOpen(false);
      await loadTenants();
    } catch (error) {
      setFormError(getApiError(error, "Unable to save business"));
    } finally {
      setIsSaving(false);
    }
  }

  /* ── Actions ───────────────────────────────────────────────────── */

  async function toggleStatus(tenant: Tenant) {
    try {
      if (tenant.is_active) {
        await deactivateTenant(tenant.id);
        toast.success("Business deactivated");
      } else {
        await activateTenant(tenant.id);
        toast.success("Business activated");
      }
      await loadTenants();
    } catch (error) {
      toast.error(getApiError(error, "Unable to update business status"));
    }
  }

  async function confirmDelete() {
    if (!deleteTarget) return;
    try {
      await deleteTenant(deleteTarget.id);
      toast.success("Business deleted");
      setDeleteTarget(null);
      await loadTenants();
    } catch (error) {
      toast.error(getApiError(error, "Unable to delete business"));
      setDeleteTarget(null);
    }
  }

  async function manageCatalog(tenant: Tenant) {
    try {
      await switchTenant(tenant.id);
      toast.success(`Switched to ${tenant.full_name}`);
    } catch (error) {
      toast.error(getApiError(error, "Unable to switch business context"));
    }
  }

  /* ── Render ────────────────────────────────────────────────────── */

  return (
    <div className="flex-1 overflow-auto">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 py-6 flex flex-col gap-6">
        <SummaryCards total={meta.total} active={meta.active} inactive={meta.inactive} />

        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
          <div className="relative max-w-sm flex-1">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 size-4 text-muted-foreground" />
            <Input
              placeholder="Search businesses..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="pl-9"
            />
          </div>
          <Button size="sm" onClick={openCreate}>
            <Plus className="size-4 mr-1.5" />
            Create Business
          </Button>
        </div>

        <div className="border rounded-lg">
          {isLoading ? (
            <div className="p-4 flex flex-col gap-3">
              {Array.from({ length: 4 }).map((_, i) => (
                <Skeleton key={i} className="h-12 w-full rounded-lg" />
              ))}
            </div>
          ) : filteredTenants.length === 0 ? (
            <EmptyState isSearch={!!searchQuery} onAction={openCreate} />
          ) : (
            <BusinessTable
              tenants={filteredTenants}
              onEdit={openEdit}
              onDelete={setDeleteTarget}
              onToggleStatus={toggleStatus}
              onManageCatalog={manageCatalog}
            />
          )}
        </div>
      </div>

      <BusinessFormDialog
        open={formOpen}
        onOpenChange={setFormOpen}
        mode={formMode}
        form={form}
        onFormChange={updateForm}
        onSubmit={handleSubmit}
        saving={isSaving}
        error={formError}
      />

      <DeleteConfirmDialog
        open={!!deleteTarget}
        onOpenChange={(o) => { if (!o) setDeleteTarget(null) }}
        businessName={deleteTarget?.full_name || ""}
        onConfirm={confirmDelete}
      />
    </div>
  );
}
