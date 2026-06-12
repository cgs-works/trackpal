import { useState, useEffect, useCallback } from "react";
import { useSearch } from "@tanstack/react-router";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { CreditCard, Plus, Search, X } from "lucide-react";
import { toast } from "sonner";
import { t } from "@/i18n";
import {
  listSubscriptions,
  createSubscription,
  updateSubscription,
  revealCredentials,
  getDropdownData,
  getPlansForService,
  type Subscription,
  type Client,
  type Service,
  type Plan,
  type SubscriptionCreate,
  type SubscriptionFilters,
} from "../services/subscription-api";
import {
  SubscriptionTable,
  RevealCredentialsDialog,
} from "./subscription-table";
import { SubscriptionFormDialog } from "./subscription-form-dialog";

export function SubscriptionsPage() {
  const STATUS_OPTIONS = [
    { value: "all", label: t("frontend.subscriptions.all_statuses") },
    { value: "active", label: t("frontend.subscriptions.status_active") },
    { value: "expired", label: t("frontend.subscriptions.status_expired") },
    { value: "cancelled", label: t("frontend.subscriptions.status_cancelled") },
  ];

  // URL search params for client_id filter
  let urlClientId: string | undefined;
  try {
    const search = useSearch({ strict: false }) as { client_id?: string };
    urlClientId = search?.client_id;
  } catch {
    // not on a route with search params
  }

  // Data
  const [subscriptions, setSubscriptions] = useState<Subscription[]>([]);
  const [clients, setClients] = useState<Client[]>([]);
  const [services, setServices] = useState<Service[]>([]);
  const [plans, setPlans] = useState<Plan[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState("");
  const [loadingPlans, setLoadingPlans] = useState(false);

  // Filters
  const [statusFilter, setStatusFilter] = useState("all");
  const [serviceFilter, setServiceFilter] = useState("all");
  const [search, setSearch] = useState("");
  const [clientIdFilter, setClientIdFilter] = useState(urlClientId || "");

  // Form state
  const [formOpen, setFormOpen] = useState(false);
  const [formMode, setFormMode] = useState<"create" | "edit">("create");
  const [selectedSub, setSelectedSub] = useState<Subscription | null>(null);
  const [saving, setSaving] = useState(false);
  const [formError, setFormError] = useState("");

  // Reveal state
  const [revealOpen, setRevealOpen] = useState(false);
  const [revealEmail, setRevealEmail] = useState("");
  const [revealPassword, setRevealPassword] = useState<string | null>(null);
  const [revealPin, setRevealPin] = useState<string | null>(null);

  // ── Load data ──────────────────────────────────────────────
  const loadDropdowns = useCallback(async () => {
    try {
      const { clients: c, services: s } = await getDropdownData();
      setClients(c);
      setServices(s);
    } catch {
      // Non-critical
    }
  }, []);

  const loadSubscriptions = useCallback(async () => {
    setIsLoading(true);
    setError("");
    try {
      const filters: SubscriptionFilters = {};
      if (statusFilter !== "all") filters.status = statusFilter;
      if (serviceFilter !== "all") filters.service_id = serviceFilter;
      if (clientIdFilter) filters.client_id = clientIdFilter;
      const data = await listSubscriptions(filters);
      setSubscriptions(data);
    } catch (err) {
      setError(
        err instanceof Error ? err.message : t("frontend.subscriptions.error_load")
      );
    } finally {
      setIsLoading(false);
    }
  }, [statusFilter, serviceFilter, clientIdFilter]);

  useEffect(() => {
    loadDropdowns();
  }, [loadDropdowns]);

  useEffect(() => {
    loadSubscriptions();
  }, [loadSubscriptions]);

  // ── Load plans when service changes for form ───────────────
  async function handleServiceChange(serviceId: string) {
    setLoadingPlans(true);
    try {
      const data = await getPlansForService(serviceId);
      setPlans(data);
    } catch {
      setPlans([]);
    } finally {
      setLoadingPlans(false);
    }
  }

  // ── Build lookup maps ──────────────────────────────────────
  const clientMap = Object.fromEntries(
    clients.map((c) => [c.id, c.full_name])
  );
  const serviceMap = Object.fromEntries(
    services.map((s) => [s.id, s.name])
  );
  // Load all plans for plan name lookup
  const [allPlans, setAllPlans] = useState<Plan[]>([]);
  useEffect(() => {
    async function loadAllPlans() {
      try {
        const all: Plan[] = [];
        for (const s of services) {
          const p = await getPlansForService(s.id);
          all.push(...p);
        }
        setAllPlans(all);
      } catch {
        // Non-critical
      }
    }
    if (services.length > 0) loadAllPlans();
  }, [services]);
  const planMap = Object.fromEntries(allPlans.map((p) => [p.id, p.name]));

  // ── Create ─────────────────────────────────────────────────
  function openCreate() {
    setFormMode("create");
    setSelectedSub(null);
    setFormError("");
    setPlans([]);
    setFormOpen(true);
  }

  // ── Edit ───────────────────────────────────────────────────
  function openEdit(sub: Subscription) {
    setFormMode("edit");
    setSelectedSub(sub);
    setFormError("");
    // Load plans for the subscription's service
    handleServiceChange(sub.service_id);
    setFormOpen(true);
  }

  async function handleSubmit(payload: SubscriptionCreate) {
    setSaving(true);
    setFormError("");
    try {
      if (formMode === "create") {
        await createSubscription(payload);
        toast.success(t("frontend.subscriptions.created"));
      } else {
        await updateSubscription(selectedSub!.id, payload);
        toast.success(t("frontend.subscriptions.updated"));
      }
      setFormOpen(false);
      await loadSubscriptions();
    } catch (err: unknown) {
      const apiErr = err as {
        response?: { data?: { detail?: string | Array<{ msg?: string }> } }
      };
      const detail = apiErr.response?.data?.detail;
      let msg = t("frontend.subscriptions.error_save");
      if (typeof detail === "string") {
        msg = detail;
      } else if (Array.isArray(detail) && detail.length > 0) {
        msg = detail.map((d) => d.msg || "Unknown error").join("; ");
      } else if (err instanceof Error) {
        msg = err.message;
      }
      setFormError(msg);
    } finally {
      setSaving(false);
    }
  }

  // ── Reveal credentials ─────────────────────────────────────
  async function handleReveal(sub: Subscription) {
    try {
      const creds = await revealCredentials(sub.id);
      setRevealEmail(sub.streaming_email);
      setRevealPassword(creds.streaming_password);
      setRevealPin(creds.profile_pin);
      setRevealOpen(true);
    } catch (err) {
      toast.error(
        err instanceof Error ? err.message : t("frontend.subscriptions.error_reveal")
      );
    }
  }

  // ── Clear filters ──────────────────────────────────────────
  const hasFilters =
    statusFilter !== "all" || serviceFilter !== "all" || clientIdFilter || search;

  return (
    <div className="flex-1 p-6">
      <div className="max-w-5xl mx-auto space-y-6">
        {/* Header */}
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-bold tracking-tight">{t("frontend.subscriptions.title")}</h1>
            <p className="text-muted-foreground">
              {t("frontend.subscriptions.section_heading")}
            </p>
          </div>
          <Button onClick={openCreate}>
            <Plus className="size-4 mr-2" />
            {t("frontend.subscriptions.new")}
          </Button>
        </div>

        {/* Filters */}
        <div className="flex flex-wrap items-center gap-3">
          <div className="relative flex-1 min-w-[200px] max-w-sm">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 size-4 text-muted-foreground" />
            <Input
              placeholder={t("frontend.subscriptions.search")}
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              className="pl-9"
            />
          </div>

          <Select value={statusFilter} onValueChange={(v) => setStatusFilter(v ?? "")}>
            <SelectTrigger className="w-[140px]">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {STATUS_OPTIONS.map((opt) => (
                <SelectItem key={opt.value} value={opt.value}>
                  {opt.label}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>

          <Select value={serviceFilter} onValueChange={(v) => setServiceFilter(v ?? "")}>
            <SelectTrigger className="w-[160px]">
              <SelectValue placeholder={t("frontend.subscriptions.all_services")} />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">{t("frontend.subscriptions.all_services")}</SelectItem>
              {services.map((s) => (
                <SelectItem key={s.id} value={s.id}>
                  {s.name}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>

          {hasFilters && (
            <Button
              variant="ghost"
              size="sm"
              onClick={() => {
                setStatusFilter("all");
                setServiceFilter("all");
                setClientIdFilter("");
                setSearch("");
              }}
            >
              <X className="size-3.5 mr-1" />
              {t("frontend.subscriptions.clear_filters")}
            </Button>
          )}
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
              {t("frontend.subscriptions.loading")}
            </div>
          </div>
        ) : subscriptions.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-12 text-center">
            <CreditCard className="size-12 text-muted-foreground/50 mb-4" />
            <h3 className="text-lg font-medium">
              {hasFilters ? t("frontend.subscriptions.no_results") : t("frontend.subscriptions.no_results")}
            </h3>
            <p className="text-muted-foreground mt-1">
              {hasFilters
                ? t("frontend.subscriptions.filter_hint")
                : t("frontend.subscriptions.create_first")}}
            </p>
            {!hasFilters && (
              <Button onClick={openCreate} className="mt-4">
                <Plus className="size-4 mr-2" />
                {t("frontend.subscriptions.new")}
              </Button>
            )}
          </div>
        ) : (
          <>
            <div className="text-sm text-muted-foreground">
              {subscriptions.length} subscription
              {subscriptions.length !== 1 ? "s" : ""}
            </div>
            <SubscriptionTable
              subscriptions={subscriptions}
              clients={clientMap}
              services={serviceMap}
              plans={planMap}
              onEdit={openEdit}
              onReveal={handleReveal}
            />
          </>
        )}
      </div>

      {/* Form dialog */}
      <SubscriptionFormDialog
        open={formOpen}
        onOpenChange={setFormOpen}
        mode={formMode}
        subscription={selectedSub}
        clients={clients}
        services={services}
        plans={plans}
        loadingPlans={loadingPlans}
        onSubmit={handleSubmit}
        saving={saving}
        error={formError}
      />

      {/* Reveal credentials dialog */}
      <RevealCredentialsDialog
        open={revealOpen}
        onOpenChange={setRevealOpen}
        email={revealEmail}
        password={revealPassword}
        pin={revealPin}
      />
    </div>
  );
}
