import { useState, useEffect, useCallback } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Badge } from "@/components/ui/badge";
import { Separator } from "@/components/ui/separator";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import {
  Package,
  Plus,
  Pencil,
  Trash2,
  AlertCircle,
} from "lucide-react";
import { toast } from "sonner";
import { t } from "@/i18n";
import { ServiceIcon } from "@/features/catalog/components/service-icon";
import type {
  Service,
  Plan,
  DeletePreview,
  ServiceCreate,
  ServiceUpdate,
  CurrencyMeta,
} from "../services/catalog-api";
import { formatPrice } from "../services/catalog-api";
import { useCatalogStore } from "@/store/catalog";
import { useAuthStore } from "@/store/auth";
import { useSettingsStore } from "@/store/settings";
import { ServiceFormDialog } from "./service-form-dialog";

const CATALOG_ERROR_KEYS: Record<string, string> = {
  service_name_already_exists: "frontend.catalog.service_name_exists",
  plan_name_already_exists: "frontend.catalog.plan_name_exists",
  catalog_name_required: "frontend.catalog.invalid_name",
  catalog_name_too_long: "frontend.catalog.invalid_name",
  catalog_icon_invalid: "frontend.catalog.invalid_icon",
  plan_price_invalid: "frontend.catalog.invalid_price",
  invalid_icon_reference: "frontend.catalog.invalid_icon",
  service_not_found: "frontend.catalog.target_not_found",
  plan_not_found: "frontend.catalog.target_not_found",
  invalid_demo_workspace: "frontend.catalog.target_not_found",
};

function catalogErrorMessage(error: unknown, fallbackKey: string): string {
  // Try to find a known error code from various sources
  if (error && typeof error === "object") {
    // 1. Check error.code first
    if ("code" in error && typeof error.code === "string") {
      const key = CATALOG_ERROR_KEYS[error.code];
      if (key) return t(key);
    }

    // 2. Check error.message for known keys
    if ("message" in error && typeof error.message === "string") {
      const key = CATALOG_ERROR_KEYS[error.message];
      if (key) return t(key);
    }

    // 3. Check Axios response.data.detail for known keys
    if (
      "response" in error &&
      error.response &&
      typeof error.response === "object" &&
      "data" in error.response
    ) {
      const data = error.response.data;
      if (data && typeof data === "object" && "detail" in data) {
        const detail = data.detail;
        // Bare string detail: "invalid_icon_reference"
        if (typeof detail === "string") {
          const key = CATALOG_ERROR_KEYS[detail];
          if (key) return t(key);
        }
        // Pydantic validation error array:
        // [{ type: "value_error", loc: [...], msg: "Value error, invalid_icon_reference" }]
        if (Array.isArray(detail)) {
          for (const item of detail) {
            if (item && typeof item === "object" && "msg" in item && typeof item.msg === "string") {
              // Check if any known error key appears in the msg
              for (const [errorCode, i18nKey] of Object.entries(CATALOG_ERROR_KEYS)) {
                if (item.msg.includes(errorCode)) return t(i18nKey);
              }
            }
          }
        }
      }
    }
  }

  // Fallback to error.message if available (unmapped error)
  if (error instanceof Error && error.message) {
    return error.message;
  }

  return t(fallbackKey);
}

// ── Price display helper ──────────────────────────────────────
function useCurrencyMeta(): CurrencyMeta | null {
  const tenantSettings = useSettingsStore((s) => s.tenantSettings);
  const currencyOptions = useSettingsStore((s) => s.currencyOptions);
  if (!tenantSettings?.currency || !currencyOptions) return null;
  return (
    currencyOptions.currencies.find(
      (c) => c.code === tenantSettings.currency,
    ) ?? null
  );
}

function useLocale(): string {
  const tenantSettings = useSettingsStore((s) => s.tenantSettings);
  return tenantSettings?.locale ?? navigator.language;
}

function PlanPriceDisplay({ price }: { price: string | null }) {
  const currencyMeta = useCurrencyMeta();
  const locale = useLocale();

  if (!price) {
    return (
      <span className="text-sm text-muted-foreground italic">
        {t("frontend.catalog.price_on_request")}
      </span>
    );
  }

  if (!currencyMeta) {
    return <span className="text-sm font-medium">{price}</span>;
  }

  return (
    <span className="text-sm font-medium">
      {formatPrice(price, currencyMeta, locale)}
    </span>
  );
}

// ── Edit Plan Dialog ──────────────────────────────────────────
interface EditPlanDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  currentName: string;
  currentPrice: string | null;
  onSave: (name: string, price: string | null) => Promise<void>;
  saving: boolean;
}

function EditPlanDialog({
  open,
  onOpenChange,
  currentName,
  currentPrice,
  onSave,
  saving,
}: EditPlanDialogProps) {
  const [name, setName] = useState(currentName);
  const [price, setPrice] = useState(currentPrice ?? "");

  useEffect(() => {
    if (open) {
      setName(currentName);
      setPrice(currentPrice ?? "");
    }
  }, [open, currentName, currentPrice]);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!name.trim()) return;
    const trimmedPrice = price.trim();
    await onSave(name.trim(), trimmedPrice ? trimmedPrice : null);
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-sm">
        <DialogHeader>
          <DialogTitle>{t("frontend.catalog.rename_plan_prompt")}</DialogTitle>
        </DialogHeader>
        <form onSubmit={handleSubmit} className="space-y-4">
          <div className="space-y-2">
            <Label htmlFor="edit-plan-name">{t("frontend.common.name")}</Label>
            <Input
              id="edit-plan-name"
              value={name}
              onChange={(e) => setName(e.target.value)}
              autoFocus
            />
          </div>
          <div className="space-y-2">
            <Label htmlFor="edit-plan-price">{t("frontend.catalog.price")}</Label>
            <Input
              id="edit-plan-price"
              type="text"
              inputMode="decimal"
              placeholder={t("frontend.catalog.price_placeholder")}
              value={price}
              onChange={(e) => setPrice(e.target.value)}
            />
          </div>
          <DialogFooter>
            <Button
              type="button"
              variant="outline"
              onClick={() => onOpenChange(false)}
              disabled={saving}
            >
              {t("frontend.common.cancel")}
            </Button>
            <Button type="submit" disabled={saving || !name.trim()}>
              {saving ? t("frontend.catalog.saving") : t("frontend.catalog.rename")}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}

// ── Delete Preview Dialog ──────────────────────────────────────
interface DeletePreviewDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  preview: DeletePreview | null;
  loading: boolean;
  error: string;
  onConfirm: () => Promise<void>;
  deleting: boolean;
}

function DeletePreviewDialog({
  open,
  onOpenChange,
  preview,
  loading,
  error,
  onConfirm,
  deleting,
}: DeletePreviewDialogProps) {
  const [confirmText, setConfirmText] = useState("");
  const canDelete = confirmText.toLowerCase() === "delete";

  useEffect(() => {
    if (open) setConfirmText("");
  }, [open]);

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-lg max-h-[90vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle>
            {preview?.target_type === "service"
              ? t("frontend.catalog.delete_preview_title_service")
              : t("frontend.catalog.delete_preview_title_plan")}
          </DialogTitle>
          <DialogDescription>
            {t("frontend.catalog.delete_preview_note")}
          </DialogDescription>
        </DialogHeader>

        {error && (
          <div className="rounded-lg bg-destructive/10 border border-destructive/20 p-3 text-sm text-destructive flex items-start gap-2">
            <AlertCircle className="size-4 mt-0.5 shrink-0" />
            {error}
          </div>
        )}

        {loading ? (
          <div className="flex items-center justify-center py-8 text-muted-foreground">
            <div className="flex items-center gap-3">
              <div className="size-5 border-2 border-border border-t-primary rounded-full animate-spin" />
              {t("frontend.catalog.delete_preview_loading")}
            </div>
          </div>
        ) : preview ? (
          <div className="space-y-4">
            <div>
              <p className="font-medium text-lg">{preview.target_name}</p>
            </div>

            <div className="grid grid-cols-2 gap-3">
              {preview.target_type === "service" && (
                <div className="rounded-lg bg-muted p-3">
                  <p className="text-2xl font-bold">
                    {preview.affected_plan_count}
                  </p>
                  <p className="text-sm text-muted-foreground">
                    {t("frontend.catalog.affected_plans")}
                  </p>
                </div>
              )}
              <div className="rounded-lg bg-muted p-3">
                <p className="text-2xl font-bold">
                  {preview.active_subscription_count}
                </p>
                <p className="text-sm text-muted-foreground">
                  {t("frontend.catalog.active_subscriptions")}
                </p>
              </div>
              <div className="rounded-lg bg-muted p-3">
                <p className="text-2xl font-bold">
                  {preview.historical_subscription_count}
                </p>
                <p className="text-sm text-muted-foreground">{t("frontend.catalog.historical_subscriptions")}</p>
              </div>
              <div className="rounded-lg bg-muted p-3">
                <p className="text-2xl font-bold">
                  {preview.total_subscription_count}
                </p>
                <p className="text-sm text-muted-foreground">{t("frontend.catalog.total_subscriptions")}</p>
              </div>
            </div>

            {preview.active_subscriptions.length > 0 && (
              <div className="space-y-2">
                <p className="text-sm font-medium">{t("frontend.catalog.active_subscriptions")}:</p>
                <div className="max-h-40 overflow-y-auto space-y-1">
                  {preview.active_subscriptions.map((sub) => (
                    <div
                      key={sub.id}
                      className="text-sm rounded bg-muted/50 p-2 flex items-center justify-between"
                    >
                      <span className="font-mono text-xs">
                        {sub.streaming_email}
                      </span>
                      <span className="text-muted-foreground">
                        {sub.client_name || "—"}
                      </span>
                    </div>
                  ))}
                </div>
                {preview.pagination.total_pages > 1 && (
                  <p className="text-xs text-muted-foreground">
                    {t("frontend.catalog.preview_page", {
                      page: preview.pagination.page,
                      total: preview.pagination.total_pages,
                    })}
                  </p>
                )}
              </div>
            )}

            <Separator />

            <div className="space-y-2">
              <Label htmlFor="confirm-delete">
                {t("frontend.catalog.confirm_label")}
              </Label>
              <Input
                id="confirm-delete"
                placeholder={t("frontend.catalog.confirm_placeholder")}
                value={confirmText}
                onChange={(e) => setConfirmText(e.target.value)}
              />
            </div>

            {preview.note && (
              <p className="text-xs text-muted-foreground italic">
                {t(preview.note)}
              </p>
            )}
          </div>
        ) : null}

        <DialogFooter>
          <Button
            type="button"
            variant="outline"
            onClick={() => onOpenChange(false)}
            disabled={deleting}
          >
            {t("frontend.common.cancel")}
          </Button>
          <Button
            variant="destructive"
            onClick={onConfirm}
            disabled={!canDelete || deleting || loading}
          >
            {deleting ? t("frontend.catalog.deleting") : t("frontend.catalog.confirm_delete")}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

// ── Main Catalog Page ──────────────────────────────────────────
export function CatalogPage() {
  const { dataSource } = useAuthStore();
  const {
    services,
    loadServices,
    loadPlans,
    invalidateServices,
    invalidatePlans,
  } = useCatalogStore();
  const [selectedServiceId, setSelectedServiceId] = useState<string>("");
  const [plans, setPlans] = useState<Plan[]>([]);
  const [isLoading, setIsLoading] = useState(!useCatalogStore.getState().servicesLoaded);
  const [error, setError] = useState("");

  // Service form state
  const [serviceFormOpen, setServiceFormOpen] = useState(false);
  const [serviceFormMode, setServiceFormMode] = useState<"create" | "edit">("create");
  const [serviceFormTarget, setServiceFormTarget] = useState<Service | null>(null);
  const [serviceSaving, setServiceSaving] = useState(false);
  const [serviceFormError, setServiceFormError] = useState("");

  // Create plan form
  const [newPlanName, setNewPlanName] = useState("");
  const [newPlanPrice, setNewPlanPrice] = useState("");
  const [creatingPlan, setCreatingPlan] = useState(false);

  // Edit plan state
  const [editPlanOpen, setEditPlanOpen] = useState(false);
  const [editPlanTarget, setEditPlanTarget] = useState<Plan | null>(null);
  const [editPlanSaving, setEditPlanSaving] = useState(false);

  // Delete state
  const [deleteOpen, setDeleteOpen] = useState(false);
  const [deletePreview, setDeletePreview] = useState<DeletePreview | null>(
    null
  );
  const [deleteLoading, setDeleteLoading] = useState(false);
  const [deleteError, setDeleteError] = useState("");
  const [deleting, setDeleting] = useState(false);
  const [deleteCallback, setDeleteCallback] = useState<
    (() => Promise<void>) | null
  >(null);

  // ── Load services ──────────────────────────────────────────
  const loadServicesData = useCallback(async () => {
    setIsLoading(true);
    setError("");
    try {
      const data = await loadServices(dataSource.catalog);
      if (!selectedServiceId && data.length > 0) {
        setSelectedServiceId(data[0].id);
      }
    } catch (err) {
      setError(
        catalogErrorMessage(err, "frontend.catalog.error_load_services")
      );
    } finally {
      setIsLoading(false);
    }
  }, [loadServices, selectedServiceId, dataSource.catalog]);

  useEffect(() => {
    loadServicesData();
  }, [loadServicesData]);

  // ── Load plans when service changes ────────────────────────
  const loadPlansData = useCallback(async () => {
    if (!selectedServiceId) {
      setPlans([]);
      return;
    }
    try {
      const data = await loadPlans(selectedServiceId, dataSource.catalog);
      setPlans(data);
    } catch (err) {
      setError(
        catalogErrorMessage(err, "frontend.catalog.error_load_plans")
      );
    }
  }, [selectedServiceId, loadPlans, dataSource.catalog]);

  useEffect(() => {
    loadPlansData();
  }, [loadPlansData]);

  // ── Service form submit ────────────────────────────────────
  async function handleServiceFormSubmit(payload: ServiceCreate | ServiceUpdate) {
    setServiceSaving(true);
    setServiceFormError("");
    try {
      if (serviceFormMode === "create") {
        const service = await dataSource.catalog.createService(payload as ServiceCreate);
        setSelectedServiceId(service.id);
        invalidateServices();
        await loadServicesData();
        toast.success(t("frontend.catalog.service_created"));
      } else if (serviceFormTarget) {
        await dataSource.catalog.updateService(serviceFormTarget.id, payload as ServiceUpdate);
        invalidateServices();
        await loadServicesData();
        toast.success(t("frontend.catalog.service_updated"));
      }
      setServiceFormOpen(false);
    } catch (err) {
      const msg = catalogErrorMessage(err, "frontend.catalog.error_update_service");
      if (
        err instanceof Error ||
        (err && typeof err === "object" && "response" in err)
      ) {
        setServiceFormError(msg);
      } else {
        toast.error(msg);
      }
    } finally {
      setServiceSaving(false);
    }
  }

  function openCreateServiceForm() {
    setServiceFormMode("create");
    setServiceFormTarget(null);
    setServiceFormError("");
    setServiceFormOpen(true);
  }

  function openEditServiceForm(service: Service) {
    setServiceFormMode("edit");
    setServiceFormTarget(service);
    setServiceFormError("");
    setServiceFormOpen(true);
  }

  // ── Create plan ────────────────────────────────────────────
  async function handleCreatePlan(e: React.FormEvent) {
    e.preventDefault();
    if (!newPlanName.trim() || !selectedServiceId) return;
    setCreatingPlan(true);
    try {
      const trimmedPrice = newPlanPrice.trim();
      await dataSource.catalog.createPlan(selectedServiceId, {
        name: newPlanName.trim(),
        price: trimmedPrice ? trimmedPrice : null,
      });
      setNewPlanName("");
      setNewPlanPrice("");
      invalidatePlans(selectedServiceId);
      await loadPlansData();
      toast.success(t("frontend.catalog.plan_created"));
    } catch (err) {
      toast.error(
        catalogErrorMessage(err, "frontend.catalog.error_create_plan")
      );
    } finally {
      setCreatingPlan(false);
    }
  }

  // ── Edit plan ──────────────────────────────────────────────
  function openEditPlan(plan: Plan) {
    setEditPlanTarget(plan);
    setEditPlanOpen(true);
  }

  async function handleEditPlanSave(name: string, price: string | null) {
    if (!editPlanTarget || !selectedServiceId) return;
    setEditPlanSaving(true);
    try {
      await dataSource.catalog.updatePlan(selectedServiceId, editPlanTarget.id, { name, price });
      invalidatePlans(selectedServiceId);
      await loadPlansData();
      toast.success(t("frontend.catalog.plan_renamed"));
      setEditPlanOpen(false);
    } catch (err) {
      toast.error(
        catalogErrorMessage(err, "frontend.catalog.error_update_plan")
      );
    } finally {
      setEditPlanSaving(false);
    }
  }

  // ── Delete service ─────────────────────────────────────────
  async function openDeleteService(service: Service) {
    setDeleteOpen(true);
    setDeleteLoading(true);
    setDeleteError("");
    setDeletePreview(null);
    try {
      const preview = await dataSource.catalog.getServiceDeletePreview(service.id);
      setDeletePreview(preview);
      setDeleteCallback(() => async () => {
        setDeleting(true);
        try {
          await dataSource.catalog.deleteService(service.id);
          if (selectedServiceId === service.id) {
            setSelectedServiceId("");
          }
          invalidateServices();
          await loadServicesData();
          toast.success(t("frontend.catalog.service_deleted"));
          setDeleteOpen(false);
        } catch (err) {
          setDeleteError(
            catalogErrorMessage(err, "frontend.catalog.error_delete_service")
          );
        } finally {
          setDeleting(false);
        }
      });
    } catch (err) {
      setDeleteError(
        catalogErrorMessage(err, "frontend.catalog.delete_preview_error")
      );
    } finally {
      setDeleteLoading(false);
    }
  }

  // ── Delete plan ────────────────────────────────────────────
  async function openDeletePlan(plan: Plan) {
    setDeleteOpen(true);
    setDeleteLoading(true);
    setDeleteError("");
    setDeletePreview(null);
    try {
      const preview = await dataSource.catalog.getPlanDeletePreview(selectedServiceId, plan.id);
      setDeletePreview(preview);
      setDeleteCallback(() => async () => {
        setDeleting(true);
        try {
          await dataSource.catalog.deletePlan(selectedServiceId, plan.id);
          invalidatePlans(selectedServiceId);
          await loadPlansData();
          toast.success(t("frontend.catalog.plan_deleted"));
          setDeleteOpen(false);
        } catch (err) {
          setDeleteError(
            catalogErrorMessage(err, "frontend.catalog.error_delete_plan")
          );
        } finally {
          setDeleting(false);
        }
      });
    } catch (err) {
      setDeleteError(
        catalogErrorMessage(err, "frontend.catalog.delete_preview_error")
      );
    } finally {
      setDeleteLoading(false);
    }
  }

  return (
    <div className="flex-1 p-6" data-help-id="admin.catalog">
      <div className="max-w-5xl mx-auto space-y-6">
        {/* Header */}
        <div>
          <h1 className="text-2xl font-bold tracking-tight">{t("frontend.catalog.section_title")}</h1>
          <p className="text-muted-foreground">
            {t("frontend.catalog.section_heading")}
          </p>
        </div>

        {/* Error */}
        {error && (
          <div className="rounded-lg bg-destructive/10 border border-destructive/20 p-3 text-sm text-destructive flex items-start gap-2">
            <AlertCircle className="size-4 mt-0.5 shrink-0" />
            {error}
          </div>
        )}

        <div className="grid md:grid-cols-[280px_1fr] gap-6">
          {/* ── Services sidebar ────────────────────────────── */}
          <div className="space-y-4">
            <div>
              <h2 className="text-sm font-medium text-muted-foreground mb-2">
                {t("frontend.catalog.services")}
              </h2>
              <Button
                variant="outline"
                className="w-full justify-start gap-2"
                data-testid="new-service-btn"
                onClick={openCreateServiceForm}
              >
                <Plus className="size-4" />
                {t("frontend.catalog.new_service")}
              </Button>
            </div>

            {isLoading ? (
              <div className="space-y-2">
                {[1, 2, 3].map((i) => (
                  <div key={i} className="h-10 rounded-lg bg-muted animate-pulse" />
                ))}
              </div>
            ) : services.length === 0 ? (
              <div className="text-center py-8 text-muted-foreground">
                <Package className="size-8 mx-auto mb-2 opacity-50" />
                <p className="text-sm">{t("frontend.catalog.no_services")}</p>
                <p className="text-xs">{t("frontend.catalog.create_service_help")}</p>
              </div>
            ) : (
              <div className="space-y-1">
                {services.map((service) => (
                  <div
                    key={service.id}
                    className={`flex items-center gap-2 p-2 rounded-lg cursor-pointer transition-colors ${
                      selectedServiceId === service.id
                        ? "bg-primary text-primary-foreground"
                        : "hover:bg-accent"
                    }`}
                    onClick={() => setSelectedServiceId(service.id)}
                  >
                    <ServiceIcon
                      icon={service.icon}
                      label={service.name}
                      className="size-4 shrink-0"
                    />
                    <span className="flex-1 truncate text-sm font-medium">
                      {service.name}
                    </span>
                    <Button
                      variant="ghost"
                      size="icon"
                      className="size-6 shrink-0"
                      aria-label={t("frontend.catalog.edit")}
                      onClick={(e) => {
                        e.stopPropagation();
                        openEditServiceForm(service);
                      }}
                    >
                      <Pencil className="size-3" />
                    </Button>
                    <Button
                      variant="ghost"
                      size="icon"
                      className="size-6 shrink-0 text-destructive hover:text-destructive"
                      onClick={(e) => {
                        e.stopPropagation();
                        openDeleteService(service);
                      }}
                    >
                      <Trash2 className="size-3" />
                    </Button>
                  </div>
                ))}
              </div>
            )}
          </div>

          {/* ── Plans panel ─────────────────────────────────── */}
          <div className="space-y-4">
            {selectedServiceId ? (
              <>
                <div>
                  <h2 className="text-sm font-medium text-muted-foreground mb-2">
                    {t("frontend.catalog.plans")}
                  </h2>
                  <form onSubmit={handleCreatePlan} className="space-y-2">
                    <div className="flex gap-2">
                      <Input
                        placeholder={t("frontend.catalog.new_plan_placeholder")}
                        value={newPlanName}
                        onChange={(e) => setNewPlanName(e.target.value)}
                        className="flex-1"
                      />
                      <Button
                        type="submit"
                        size="icon"
                        disabled={creatingPlan || !newPlanName.trim()}
                      >
                        <Plus className="size-4" />
                      </Button>
                    </div>
                    <Input
                      type="text"
                      inputMode="decimal"
                      placeholder={t("frontend.catalog.price_placeholder")}
                      value={newPlanPrice}
                      onChange={(e) => setNewPlanPrice(e.target.value)}
                      aria-label={t("frontend.catalog.price")}
                    />
                  </form>
                </div>

                {plans.length === 0 ? (
                  <div className="text-center py-12 text-muted-foreground border rounded-lg">
                    <Package className="size-8 mx-auto mb-2 opacity-50" />
                    <p className="text-sm">{t("frontend.catalog.no_plans")}</p>
                    <p className="text-xs">{t("frontend.catalog.create_plan_help")}</p>
                  </div>
                ) : (
                  <div className="space-y-2">
                    {plans.map((plan) => (
                      <div
                        key={plan.id}
                        className="flex items-center justify-between p-3 rounded-lg border bg-card"
                      >
                        <div className="flex items-center gap-3">
                          <div className="size-8 rounded bg-muted flex items-center justify-center">
                            <Badge variant="secondary" className="font-mono text-xs">
                              {plan.name.slice(0, 2).toUpperCase()}
                            </Badge>
                          </div>
                          <span className="text-sm font-medium">
                            {plan.name}
                          </span>
                          <PlanPriceDisplay price={plan.price} />
                        </div>
                        <div className="flex items-center gap-1">
                          <Button
                            variant="ghost"
                            size="sm"
                            onClick={() => openEditPlan(plan)}
                          >
                            <Pencil className="size-3.5 mr-1" />
                            {t("frontend.catalog.rename")}
                          </Button>
                          <Button
                            variant="ghost"
                            size="sm"
                            className="text-destructive hover:text-destructive"
                            onClick={() => openDeletePlan(plan)}
                          >
                            <Trash2 className="size-3.5 mr-1" />
                            {t("frontend.catalog.delete")}
                          </Button>
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </>
            ) : (
              <div className="text-center py-12 text-muted-foreground border rounded-lg">
                <Package className="size-8 mx-auto mb-2 opacity-50" />
                <p className="text-sm">{t("frontend.catalog.select_service_help")}</p>
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Service form dialog */}
      <ServiceFormDialog
        open={serviceFormOpen}
        mode={serviceFormMode}
        service={serviceFormTarget}
        saving={serviceSaving}
        error={serviceFormError}
        onOpenChange={setServiceFormOpen}
        onSubmit={handleServiceFormSubmit}
      />

      {/* Edit plan dialog (name + price) */}
      <EditPlanDialog
        open={editPlanOpen}
        onOpenChange={setEditPlanOpen}
        currentName={editPlanTarget?.name ?? ""}
        currentPrice={editPlanTarget?.price ?? null}
        onSave={handleEditPlanSave}
        saving={editPlanSaving}
      />

      {/* Delete preview dialog */}
      <DeletePreviewDialog
        open={deleteOpen}
        onOpenChange={setDeleteOpen}
        preview={deletePreview}
        loading={deleteLoading}
        error={deleteError}
        onConfirm={async () => {
          if (deleteCallback) await deleteCallback();
        }}
        deleting={deleting}
      />
    </div>
  );
}
