import { createFileRoute } from "@tanstack/react-router";
import { useState, useEffect, useCallback } from "react";
import { toast } from "sonner";
import api from "@/lib/api";
import { useAuthStore } from "@/store/auth";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Badge } from "@/components/ui/badge";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
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
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Separator } from "@/components/ui/separator";
import { Skeleton } from "@/components/ui/skeleton";
import { StatusBar } from "@/components/status-bar";
import { CodeServicesSidebar } from "@/components/code-services-sidebar";
import {
  Plus,
  Pencil,
  Trash2,
  Power,
  Settings,
  Search,
} from "lucide-react";

export const Route = createFileRoute("/master/dashboard")({
  component: MasterDashboard,
});

/* ── Types ─────────────────────────────────────────────────────── */

interface Tenant {
  id: string;
  full_name: string;
  client_prefix: string;
  email: string | null;
  phone: string | null;
  evolution_instance_name: string | null;
  is_active: boolean;
  username: string;
  created_at: string;
}

interface TenantMeta {
  total: number;
  active: number;
  inactive: number;
}

interface TenantListResponse {
  data: Tenant[];
  meta: TenantMeta;
}

interface CodeService {
  service_key: string;
  label: string;
  is_active: boolean;
}

interface EmptyForm {
  id: string | null;
  full_name: string;
  email: string;
  phone: string;
  client_prefix: string;
  username: string;
  password: string;
  evolution_instance_name: string;
}

/* ── Helpers ────────────────────────────────────────────────────── */

function getEmptyForm(): EmptyForm {
  return {
    id: null,
    full_name: "",
    email: "",
    phone: "",
    client_prefix: "",
    username: "",
    password: "",
    evolution_instance_name: "",
  };
}

function getApiError(error: unknown, fallback: string): string {
  const err = error as {
    response?: { data?: { detail?: string | Array<{ msg?: string }> } };
  };
  const detail = err.response?.data?.detail;
  if (Array.isArray(detail)) {
    return detail.map((item) => item.msg || String(item)).join(", ");
  }
  return (typeof detail === "string" ? detail : null) || fallback;
}

function isTenantActive(tenant: Tenant): boolean {
  return tenant.is_active;
}

function getGeneratedPassword(data: unknown): string {
  const d = data as Record<string, unknown>;
  return (
    (d?.generated_password as string) ||
    (d?.password as string) ||
    (d?.temporary_password as string) ||
    (d?.plain_password as string) ||
    ""
  );
}

/* ── Component ─────────────────────────────────────────────────── */

function MasterDashboard() {
  const { switchTenant } = useAuthStore();

  /* Tenant state */
  const [tenants, setTenants] = useState<Tenant[]>([]);
  const [meta, setMeta] = useState<TenantMeta>({ total: 0, active: 0, inactive: 0 });
  const [isLoading, setIsLoading] = useState(false);
  const [searchQuery, setSearchQuery] = useState("");

  /* Modal state */
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [modalMode, setModalMode] = useState<"create" | "edit">("create");
  const [form, setForm] = useState<EmptyForm>(getEmptyForm());
  const [isSaving, setIsSaving] = useState(false);
  const [modalError, setModalError] = useState("");

  /* Delete confirm */
  const [deleteTarget, setDeleteTarget] = useState<Tenant | null>(null);

  /* Code Services sidebar */
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [services, setServices] = useState<CodeService[]>([]);
  const [servicesLoading, setServicesLoading] = useState(false);

  const isEditMode = modalMode === "edit";
  const modalTitle = isEditMode ? "Edit Business" : "Create Business";
  const modalPrefixHint = isEditMode
    ? "Changing this prefix will update all client login usernames for this business."
    : "Leave blank to auto-generate a unique prefix.";

  /* ── Data loading ──────────────────────────────────────────────── */

  const loadTenants = useCallback(async () => {
    setIsLoading(true);
    try {
      const response = await api.get<TenantListResponse>("/tenants");
      const result = response.data;
      setTenants(result.data || []);
      setMeta(
        result.meta || {
          total: (result.data || []).length,
          active: (result.data || []).filter((t) => isTenantActive(t)).length,
          inactive: (result.data || []).filter((t) => !isTenantActive(t)).length,
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

  /* ── Code services ─────────────────────────────────────────────── */

  const loadServices = useCallback(async () => {
    setServicesLoading(true);
    try {
      const res = await api.get<{ services: CodeService[] }>("/code-services/global");
      setServices(res.data.services || []);
    } catch {
      toast.error("Unable to load code services");
    } finally {
      setServicesLoading(false);
    }
  }, []);

  useEffect(() => {
    loadServices();
  }, [loadServices]);

  async function saveServices(updatedServices: CodeService[]) {
    try {
      const payload: Record<string, boolean> = {};
      for (const svc of updatedServices) {
        payload[svc.service_key] = svc.is_active;
      }
      await api.put("/code-services/global", { services: payload });
      setServices(updatedServices);
      toast.success("Code services saved");
    } catch (error) {
      toast.error(getApiError(error, "Unable to save code services"));
      throw error; // Re-throw so sidebar can handle it
    }
  }

  /* ── Filtered tenants ─────────────────────────────────────────── */

  const filteredTenants = tenants.filter((tenant) => {
    if (!searchQuery) return true;
    const q = searchQuery.toLowerCase();
    return (
      tenant.full_name.toLowerCase().includes(q) ||
      tenant.email?.toLowerCase().includes(q) ||
      tenant.client_prefix?.toLowerCase().includes(q)
    );
  });

  /* ── Modal helpers ─────────────────────────────────────────────── */

  function openCreateModal() {
    setModalMode("create");
    setForm(getEmptyForm());
    setIsModalOpen(true);
  }

  function openEditModal(tenant: Tenant) {
    setModalMode("edit");
    setForm({
      ...getEmptyForm(),
      id: tenant.id,
      full_name: tenant.full_name || "",
      email: tenant.email || "",
      phone: tenant.phone || "",
      client_prefix: tenant.client_prefix || "",
      evolution_instance_name: tenant.evolution_instance_name || "",
    });
    setIsModalOpen(true);
  }

  function closeModal() {
    if (isSaving) return;
    setIsModalOpen(false);
    setModalError("");
  }

  function validateForm(): boolean {
    if (!form.full_name || !form.email || !form.phone) {
      setModalError("Full name, email, and phone are required.");
      return false;
    }
    if (!isEditMode && !form.username) {
      setModalError("Username is required.");
      return false;
    }
    if (!form.evolution_instance_name) {
      setModalError("Evolution instance name is required.");
      return false;
    }
    return true;
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setModalError("");
    if (!validateForm()) return;

    setIsSaving(true);
    try {
      if (isEditMode) {
        const payload: Record<string, unknown> = {
          full_name: form.full_name,
          email: form.email,
          phone: form.phone,
          evolution_instance_name: form.evolution_instance_name,
        };
        if (form.client_prefix.trim()) {
          payload.client_prefix = form.client_prefix;
        }
        await api.put(`/tenants/${form.id}`, payload);
        toast.success("Business updated");
      } else {
        const payload: Record<string, unknown> = {
          full_name: form.full_name,
          email: form.email,
          phone: form.phone,
          username: form.username,
          evolution_instance_name: form.evolution_instance_name,
        };
        if (form.client_prefix.trim()) {
          payload.client_prefix = form.client_prefix;
        }
        if (form.password) {
          payload.password = form.password;
        }
        const res = await api.post("/tenants", payload);
        const generatedPassword = getGeneratedPassword(res.data);
        toast.success(
          generatedPassword
            ? `Business created. Password: ${generatedPassword}`
            : "Business created"
        );
      }
      setIsModalOpen(false);
      await loadTenants();
    } catch (error) {
      setModalError(getApiError(error, "Unable to save business"));
    } finally {
      setIsSaving(false);
    }
  }

  function updateForm<K extends keyof EmptyForm>(key: K, value: EmptyForm[K]) {
    setForm((prev) => ({ ...prev, [key]: value }));
  }

  /* ── Actions ───────────────────────────────────────────────────── */

  async function toggleTenantStatus(tenant: Tenant) {
    const active = isTenantActive(tenant);
    const endpoint = active
      ? `/tenants/${tenant.id}/deactivate`
      : `/tenants/${tenant.id}/activate`;
    try {
      await api.patch(endpoint);
      toast.success(active ? "Business deactivated" : "Business activated");
      await loadTenants();
    } catch (error) {
      toast.error(getApiError(error, "Unable to update business status"));
    }
  }

  async function confirmDelete() {
    if (!deleteTarget) return;
    try {
      await api.delete(`/tenants/${deleteTarget.id}`);
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
      // TODO: navigate to /admin/dashboard after tenant dashboard is built
      toast.success(`Switched to ${tenant.full_name}`);
    } catch (error) {
      toast.error(getApiError(error, "Unable to switch business context"));
    }
  }

  /* ── Render ────────────────────────────────────────────────────── */

  return (
    <div className="min-h-screen bg-background">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 py-6 space-y-6">
        {/* Status bar */}
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
          <StatusBar
            total={meta.total}
            active={meta.active}
            inactive={meta.inactive}
          />
          <div className="flex items-center gap-2">
            <Button
              variant="outline"
              size="sm"
              onClick={() => setSidebarOpen(true)}
              className="hidden sm:flex"
            >
              <Settings className="h-4 w-4 mr-1.5" />
              Code Services
            </Button>
            <Button size="sm" onClick={openCreateModal}>
              <Plus className="h-4 w-4 mr-1.5" />
              Create Business
            </Button>
          </div>
        </div>

        {/* Search */}
        <div className="relative max-w-sm">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
          <Input
            placeholder="Search businesses..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="pl-9"
          />
        </div>

        {/* Businesses table */}
        <div className="border rounded-lg">
          {isLoading ? (
            <div className="p-4 space-y-3">
              {Array.from({ length: 4 }).map((_, i) => (
                <Skeleton key={i} className="h-12 w-full rounded-lg" />
              ))}
            </div>
          ) : filteredTenants.length === 0 ? (
            <div className="flex flex-col items-center justify-center py-16 text-center">
              <div className="h-12 w-12 rounded-full bg-muted flex items-center justify-center mb-4">
                <Plus className="h-6 w-6 text-muted-foreground" />
              </div>
              <p className="text-muted-foreground mb-4">
                {searchQuery
                  ? "No businesses match your search"
                  : "No businesses yet"}
              </p>
              {!searchQuery && (
                <Button size="sm" onClick={openCreateModal}>
                  <Plus className="h-4 w-4 mr-1.5" />
                  Create your first business
                </Button>
              )}
            </div>
          ) : (
            <>
              {/* Desktop table */}
              <div className="hidden md:block overflow-x-auto">
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>Business</TableHead>
                      <TableHead>Prefix</TableHead>
                      <TableHead>Contact</TableHead>
                      <TableHead>Instance</TableHead>
                      <TableHead>Status</TableHead>
                      <TableHead className="text-right">Actions</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {filteredTenants.map((tenant) => (
                      <TableRow
                        key={tenant.id}
                        className="hover:bg-muted/50 transition-colors"
                      >
                        <TableCell className="font-medium">
                          {tenant.full_name}
                        </TableCell>
                        <TableCell>
                          <Badge variant="outline" className="font-mono">
                            {tenant.client_prefix || "—"}
                          </Badge>
                        </TableCell>
                        <TableCell>
                          <div className="text-sm">
                            <div>{tenant.email}</div>
                            {tenant.phone && (
                              <div className="text-muted-foreground">
                                {tenant.phone}
                              </div>
                            )}
                          </div>
                        </TableCell>
                        <TableCell className="text-muted-foreground text-sm">
                          {tenant.evolution_instance_name || "—"}
                        </TableCell>
                        <TableCell>
                          <Badge
                            variant={
                              isTenantActive(tenant) ? "default" : "secondary"
                            }
                            className={
                              isTenantActive(tenant)
                                ? "bg-emerald-100 text-emerald-800 hover:bg-emerald-100 dark:bg-emerald-900 dark:text-emerald-300"
                                : "bg-amber-100 text-amber-800 hover:bg-amber-100 dark:bg-amber-900 dark:text-amber-300"
                            }
                          >
                            {isTenantActive(tenant) ? "Active" : "Inactive"}
                          </Badge>
                        </TableCell>
                        <TableCell className="text-right">
                          <div className="flex items-center justify-end gap-1">
                            <Button
                              variant="ghost"
                              size="sm"
                              onClick={() => openEditModal(tenant)}
                              title="Edit"
                            >
                              <Pencil className="h-3.5 w-3.5" />
                              <span className="sr-only">Edit</span>
                            </Button>
                            <Button
                              variant="ghost"
                              size="sm"
                              onClick={() => manageCatalog(tenant)}
                              title="Manage catalog"
                            >
                              <Settings className="h-3.5 w-3.5" />
                              <span className="sr-only">Manage catalog</span>
                            </Button>
                            <Button
                              variant="ghost"
                              size="sm"
                              onClick={() => toggleTenantStatus(tenant)}
                              title={
                                isTenantActive(tenant)
                                  ? "Deactivate"
                                  : "Activate"
                              }
                            >
                              <Power className="h-3.5 w-3.5" />
                              <span className="sr-only">
                                {isTenantActive(tenant)
                                  ? "Deactivate"
                                  : "Activate"}
                              </span>
                            </Button>
                            <Button
                              variant="ghost"
                              size="sm"
                              className="text-destructive hover:text-destructive"
                              onClick={() => setDeleteTarget(tenant)}
                              disabled={isTenantActive(tenant)}
                              title={
                                isTenantActive(tenant)
                                  ? "Deactivate first to delete"
                                  : "Delete"
                              }
                            >
                              <Trash2 className="h-3.5 w-3.5" />
                              <span className="sr-only">Delete</span>
                            </Button>
                          </div>
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </div>

              {/* Mobile card list */}
              <div className="md:hidden divide-y">
                {filteredTenants.map((tenant) => (
                  <div key={tenant.id} className="p-4 space-y-2">
                    <div className="flex items-start justify-between">
                      <div>
                        <p className="font-medium">{tenant.full_name}</p>
                        <p className="text-sm text-muted-foreground">
                          {tenant.email}
                        </p>
                      </div>
                      <Badge
                        variant={
                          isTenantActive(tenant) ? "default" : "secondary"
                        }
                        className={
                          isTenantActive(tenant)
                            ? "bg-emerald-100 text-emerald-800 dark:bg-emerald-900 dark:text-emerald-300"
                            : "bg-amber-100 text-amber-800 dark:bg-amber-900 dark:text-amber-300"
                        }
                      >
                        {isTenantActive(tenant) ? "Active" : "Inactive"}
                      </Badge>
                    </div>
                    <div className="text-sm text-muted-foreground space-y-0.5">
                      <p>Prefix: {tenant.client_prefix || "—"}</p>
                      <p>Phone: {tenant.phone || "—"}</p>
                      <p>Instance: {tenant.evolution_instance_name || "—"}</p>
                    </div>
                    <Separator />
                    <div className="flex items-center gap-1">
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => openEditModal(tenant)}
                      >
                        <Pencil className="h-3.5 w-3.5 mr-1" />
                        Edit
                      </Button>
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => manageCatalog(tenant)}
                      >
                        <Settings className="h-3.5 w-3.5 mr-1" />
                        Catalog
                      </Button>
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => toggleTenantStatus(tenant)}
                      >
                        <Power className="h-3.5 w-3.5 mr-1" />
                        {isTenantActive(tenant) ? "Deactivate" : "Activate"}
                      </Button>
                      <Button
                        variant="ghost"
                        size="sm"
                        className="text-destructive hover:text-destructive"
                        onClick={() => setDeleteTarget(tenant)}
                        disabled={isTenantActive(tenant)}
                      >
                        <Trash2 className="h-3.5 w-3.5 mr-1" />
                        Delete
                      </Button>
                    </div>
                  </div>
                ))}
              </div>
            </>
          )}
        </div>

        {/* Mobile Code Services button */}
        <Button
          variant="outline"
          className="sm:hidden w-full"
          onClick={() => setSidebarOpen(true)}
        >
          <Settings className="h-4 w-4 mr-1.5" />
          Code Services
        </Button>
      </div>

      {/* Code Services Sidebar */}
      <CodeServicesSidebar
        open={sidebarOpen}
        onOpenChange={setSidebarOpen}
        services={services}
        loading={servicesLoading}
        onSave={saveServices}
      />

      {/* Create / Edit Modal */}
      <Dialog open={isModalOpen} onOpenChange={(open) => { if (!open) closeModal(); }}>
        <DialogContent className="sm:max-w-md">
          <DialogHeader>
            <DialogTitle>{modalTitle}</DialogTitle>
            <DialogDescription>
              {isEditMode
                ? "Update business details and configuration."
                : "Register a new business with an Evolution instance."}
            </DialogDescription>
          </DialogHeader>

          {modalError && (
            <div className="rounded-lg bg-destructive/10 border border-destructive/20 p-3 text-sm text-destructive">
              {modalError}
            </div>
          )}

          <form onSubmit={handleSubmit} className="space-y-4">
            <div className="space-y-2">
              <Label htmlFor="full_name">Full Name</Label>
              <Input
                id="full_name"
                required
                value={form.full_name}
                onChange={(e) => updateForm("full_name", e.target.value)}
              />
            </div>

            <div className="space-y-2">
              <Label htmlFor="email">Email</Label>
              <Input
                id="email"
                type="email"
                required
                value={form.email}
                onChange={(e) => updateForm("email", e.target.value)}
              />
            </div>

            <div className="space-y-2">
              <Label htmlFor="phone">Phone</Label>
              <Input
                id="phone"
                type="tel"
                required
                value={form.phone}
                onChange={(e) => updateForm("phone", e.target.value)}
              />
            </div>

            <div className="space-y-2">
              <Label htmlFor="client_prefix">
                Client Prefix <span className="text-muted-foreground font-normal">(optional)</span>
              </Label>
              <Input
                id="client_prefix"
                maxLength={5}
                value={form.client_prefix}
                onChange={(e) => updateForm("client_prefix", e.target.value)}
              />
              <p className="text-xs text-muted-foreground">{modalPrefixHint}</p>
            </div>

            {!isEditMode && (
              <>
                <div className="space-y-2">
                  <Label htmlFor="tenant_username">Username</Label>
                  <Input
                    id="tenant_username"
                    required
                    value={form.username}
                    onChange={(e) => updateForm("username", e.target.value)}
                  />
                </div>
                <div className="space-y-2">
                  <Label htmlFor="password">
                    Password <span className="text-muted-foreground font-normal">(optional)</span>
                  </Label>
                  <Input
                    id="password"
                    type="password"
                    autoComplete="new-password"
                    value={form.password}
                    onChange={(e) => updateForm("password", e.target.value)}
                  />
                </div>
              </>
            )}

            <div className="space-y-2">
              <Label htmlFor="evolution_instance_name">Evolution Instance</Label>
              <Input
                id="evolution_instance_name"
                required
                value={form.evolution_instance_name}
                onChange={(e) =>
                  updateForm("evolution_instance_name", e.target.value)
                }
              />
            </div>

            <DialogFooter>
              <Button
                type="button"
                variant="outline"
                onClick={closeModal}
                disabled={isSaving}
              >
                Cancel
              </Button>
              <Button type="submit" disabled={isSaving}>
                {isSaving ? "Saving..." : "Save"}
              </Button>
            </DialogFooter>
          </form>
        </DialogContent>
      </Dialog>

      {/* Delete confirmation */}
      <AlertDialog
        open={!!deleteTarget}
        onOpenChange={(open) => { if (!open) setDeleteTarget(null); }}
      >
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Delete business?</AlertDialogTitle>
            <AlertDialogDescription>
              This will permanently delete <strong>{deleteTarget?.full_name}</strong>.
              This action cannot be undone.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancel</AlertDialogCancel>
            <AlertDialogAction
              onClick={confirmDelete}
              className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
            >
              Delete
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
}
