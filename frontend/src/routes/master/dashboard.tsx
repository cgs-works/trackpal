import { createFileRoute } from "@tanstack/react-router";
import { useState, useEffect, useCallback } from "react";
import api from "@/lib/api";
import { useAuthStore } from "@/store/auth";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Badge } from "@/components/ui/badge";
import { Alert, AlertDescription } from "@/components/ui/alert";
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
import {
  Building2,
  CheckCircle2,
  XCircle,
  Plus,
  Pencil,
  Trash2,
  Power,
  Settings,
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
  const [errorMessage, setErrorMessage] = useState("");
  const [successMessage, setSuccessMessage] = useState("");

  /* Modal state */
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [modalMode, setModalMode] = useState<"create" | "edit">("create");
  const [form, setForm] = useState<EmptyForm>(getEmptyForm());
  const [isSaving, setIsSaving] = useState(false);
  const [modalError, setModalError] = useState("");

  /* Delete confirm */
  const [deleteTarget, setDeleteTarget] = useState<Tenant | null>(null);

  const isEditMode = modalMode === "edit";
  const modalTitle = isEditMode ? "Edit Business" : "Create Business";
  const modalPrefixHint = isEditMode
    ? "Changing this prefix will update all client login usernames for this business."
    : "Leave blank to auto-generate a unique prefix.";

  /* ── Data loading ──────────────────────────────────────────────── */

  const loadTenants = useCallback(async () => {
    setErrorMessage("");
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
      setErrorMessage(getApiError(error, "Unable to load businesses"));
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    loadTenants();
  }, [loadTenants]);

  /* ── Code services ─────────────────────────────────────────────── */

  const [services, setServices] = useState<CodeService[]>([]);
  const [servicesLoading, setServicesLoading] = useState(false);
  const [servicesSaving, setServicesSaving] = useState(false);
  const [servicesError, setServicesError] = useState("");
  const [servicesSuccess, setServicesSuccess] = useState("");

  useEffect(() => {
    let cancelled = false;
    async function load() {
      setServicesLoading(true);
      try {
        const res = await api.get<{ services: CodeService[] }>("/code-services/global");
        if (!cancelled) setServices(res.data.services || []);
      } catch {
        if (!cancelled) setServicesError("Unable to load code services");
      } finally {
        if (!cancelled) setServicesLoading(false);
      }
    }
    load();
    return () => { cancelled = true; };
  }, []);

  function toggleService(key: string) {
    setServices((prev) =>
      prev.map((s) =>
        s.service_key === key ? { ...s, is_active: !s.is_active } : s
      )
    );
  }

  async function saveServices() {
    setServicesError("");
    setServicesSuccess("");
    setServicesSaving(true);
    try {
      const payload: Record<string, boolean> = {};
      for (const svc of services) {
        payload[svc.service_key] = svc.is_active;
      }
      await api.put("/code-services/global", { services: payload });
      setServicesSuccess("Code services saved successfully.");
    } catch {
      setServicesError("Unable to save code services");
    } finally {
      setServicesSaving(false);
    }
  }

  /* ── Modal helpers ─────────────────────────────────────────────── */

  function clearMessages() {
    setErrorMessage("");
    setSuccessMessage("");
    setModalError("");
  }

  function openCreateModal() {
    clearMessages();
    setModalMode("create");
    setForm(getEmptyForm());
    setIsModalOpen(true);
  }

  function openEditModal(tenant: Tenant) {
    clearMessages();
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
    setSuccessMessage("");
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
        setSuccessMessage("Business updated successfully.");
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
        setSuccessMessage(
          generatedPassword
            ? `Business created successfully. Generated password: ${generatedPassword}`
            : "Business created successfully."
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
    clearMessages();
    const active = isTenantActive(tenant);
    const endpoint = active
      ? `/tenants/${tenant.id}/deactivate`
      : `/tenants/${tenant.id}/activate`;
    try {
      await api.patch(endpoint);
      setSuccessMessage(
        active ? "Business deactivated successfully." : "Business activated successfully."
      );
      await loadTenants();
    } catch (error) {
      setErrorMessage(getApiError(error, "Unable to update business status"));
    }
  }

  async function confirmDelete() {
    if (!deleteTarget) return;
    clearMessages();
    try {
      await api.delete(`/tenants/${deleteTarget.id}`);
      setSuccessMessage("Business deleted successfully.");
      setDeleteTarget(null);
      await loadTenants();
    } catch (error) {
      setErrorMessage(getApiError(error, "Unable to delete business"));
      setDeleteTarget(null);
    }
  }

  async function manageCatalog(tenant: Tenant) {
    clearMessages();
    try {
      await switchTenant(tenant.id);
      // TODO: navigate to /admin/dashboard after tenant dashboard is built
      setSuccessMessage(`Switched to ${tenant.full_name} context.`);
    } catch (error) {
      setErrorMessage(getApiError(error, "Unable to switch business context"));
    }
  }

  /* ── Render ────────────────────────────────────────────────────── */

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 py-8 space-y-8">
      {/* Summary cards */}
      <section aria-label="Business summary">
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
          <SummaryCard
            icon={<Building2 className="h-5 w-5 text-muted-foreground" />}
            label="Total Businesses"
            value={meta.total}
          />
          <SummaryCard
            icon={<CheckCircle2 className="h-5 w-5 text-emerald-600" />}
            label="Active"
            value={meta.active}
          />
          <SummaryCard
            icon={<XCircle className="h-5 w-5 text-amber-600" />}
            label="Inactive"
            value={meta.inactive}
          />
        </div>
      </section>

      {/* Alerts */}
      {errorMessage && (
        <Alert variant="destructive">
          <AlertDescription>{errorMessage}</AlertDescription>
        </Alert>
      )}
      {successMessage && (
        <Alert className="border-emerald-200 bg-emerald-50 text-emerald-800 dark:border-emerald-800 dark:bg-emerald-950 dark:text-emerald-300">
          <AlertDescription>{successMessage}</AlertDescription>
        </Alert>
      )}

      {/* Businesses section */}
      <section>
        <Card>
          <CardHeader className="flex flex-row items-center justify-between gap-4">
            <div>
              <CardTitle className="text-lg">Businesses</CardTitle>
              <p className="text-sm text-muted-foreground mt-1">
                Manage business accounts and Evolution instances.
              </p>
            </div>
            <Button size="sm" onClick={openCreateModal} className="shrink-0">
              <Plus className="h-4 w-4 mr-1.5" />
              Create Business
            </Button>
          </CardHeader>
          <CardContent>
            {isLoading ? (
              <div className="space-y-3">
                {Array.from({ length: 3 }).map((_, i) => (
                  <Skeleton key={i} className="h-12 w-full rounded-lg" />
                ))}
              </div>
            ) : tenants.length === 0 ? (
              <p className="text-center text-muted-foreground py-12">
                No businesses registered yet
              </p>
            ) : (
              <>
                {/* Desktop table */}
                <div className="hidden md:block overflow-x-auto">
                  <Table>
                    <TableHeader>
                      <TableRow>
                        <TableHead>Full Name</TableHead>
                        <TableHead>Prefix</TableHead>
                        <TableHead>Email</TableHead>
                        <TableHead>Phone</TableHead>
                        <TableHead>Evolution Instance</TableHead>
                        <TableHead>Status</TableHead>
                        <TableHead className="text-right">Actions</TableHead>
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {tenants.map((tenant) => (
                        <TableRow key={tenant.id}>
                          <TableCell className="font-medium">
                            {tenant.full_name}
                          </TableCell>
                          <TableCell>
                            {tenant.client_prefix || "—"}
                          </TableCell>
                          <TableCell>{tenant.email}</TableCell>
                          <TableCell>{tenant.phone}</TableCell>
                          <TableCell>
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
                <div className="md:hidden space-y-3">
                  {tenants.map((tenant) => (
                    <div
                      key={tenant.id}
                      className="border rounded-lg p-4 space-y-2"
                    >
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
                              ? "bg-emerald-100 text-emerald-800"
                              : "bg-amber-100 text-amber-800"
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
          </CardContent>
        </Card>
      </section>

      {/* Code Services */}
      <section>
        <Card>
          <CardHeader>
            <CardTitle className="text-lg">Code Services</CardTitle>
            <p className="text-sm text-muted-foreground">
              Manage globally enabled code services for all businesses.
            </p>
          </CardHeader>
          <CardContent>
            {servicesError && (
              <Alert variant="destructive" className="mb-4">
                <AlertDescription>{servicesError}</AlertDescription>
              </Alert>
            )}
            {servicesSuccess && (
              <Alert className="mb-4 border-emerald-200 bg-emerald-50 text-emerald-800">
                <AlertDescription>{servicesSuccess}</AlertDescription>
              </Alert>
            )}
            {servicesLoading ? (
              <div className="space-y-3">
                {Array.from({ length: 2 }).map((_, i) => (
                  <Skeleton key={i} className="h-12 w-full rounded-lg" />
                ))}
              </div>
            ) : services.length === 0 ? (
              <p className="text-center text-muted-foreground py-8">
                No code services configured
              </p>
            ) : (
              <>
                <div className="space-y-2 mb-4">
                  {services.map((svc) => (
                    <div
                      key={svc.service_key}
                      className="flex items-center justify-between border rounded-lg px-4 py-3"
                    >
                      <label className="flex items-center gap-3 cursor-pointer">
                        <input
                          type="checkbox"
                          checked={svc.is_active}
                          onChange={() => toggleService(svc.service_key)}
                          className="h-4 w-4 rounded border-input accent-primary"
                        />
                        <span className="font-medium text-sm">{svc.label}</span>
                      </label>
                      <Badge
                        variant={svc.is_active ? "default" : "secondary"}
                        className={
                          svc.is_active
                            ? "bg-emerald-100 text-emerald-800"
                            : "bg-muted text-muted-foreground"
                        }
                      >
                        {svc.is_active ? "Active" : "Inactive"}
                      </Badge>
                    </div>
                  ))}
                </div>
                <div className="flex justify-end">
                  <Button
                    size="sm"
                    onClick={saveServices}
                    disabled={servicesSaving}
                  >
                    {servicesSaving ? "Saving..." : "Save Changes"}
                  </Button>
                </div>
              </>
            )}
          </CardContent>
        </Card>
      </section>

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
            <Alert variant="destructive">
              <AlertDescription>{modalError}</AlertDescription>
            </Alert>
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

/* ── Sub-components ─────────────────────────────────────────────── */

function SummaryCard({
  icon,
  label,
  value,
}: {
  icon: React.ReactNode;
  label: string;
  value: number;
}) {
  return (
    <Card>
      <CardContent className="flex items-center gap-4 p-5">
        <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-muted">
          {icon}
        </div>
        <div>
          <p className="text-sm text-muted-foreground">{label}</p>
          <p className="text-2xl font-bold tracking-tight">{value}</p>
        </div>
      </CardContent>
    </Card>
  );
}
