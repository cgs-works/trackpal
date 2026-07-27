import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import type { FormEvent } from "react";
import { Loader2, Send } from "lucide-react";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import type { Client } from "@/features/admin/services/client-api";
import type { Plan, Service } from "@/features/admin/services/catalog-api";
import type {
  Subscription,
  SubscriptionCreate,
  SubscriptionUpdate,
} from "@/features/admin/services/subscription-api";
import { t } from "@/i18n";
import { useAuthStore } from "@/store/auth";
import { usePrefersReducedMotion } from "./use-prefers-reduced-motion";

const PAGE_SIZE = 4;
const DURATION_TYPES = ["1_month", "3_months", "6_months", "9_months", "1_year", "custom"] as const;
type Filter = "all" | "active" | "expired" | "cancelled";
type Message = { id: number; role: "bot" | "user"; text: string };
type Screen =
  | "menu"
  | "filter"
  | "list"
  | "detail"
  | "create-client"
  | "create-service"
  | "create-plan"
  | "create-email"
  | "create-password"
  | "create-profile"
  | "create-pin"
  | "create-duration"
  | "create-start"
  | "create-expiry"
  | "create-confirm"
  | "edit-fields"
  | "edit-value"
  | "edit-duration"
  | "edit-duration-expiry"
  | "edit-client"
  | "edit-service"
  | "edit-plan"
  | "edit-service-plan"
  | "cancel-confirm"
  | "renew-duration"
  | "renew-expiry"
  | "reactivate-duration"
  | "reactivate-expiry";

interface SubscriptionConsoleExperienceProps {
  onBack: () => void;
  onCancel: () => void;
  onChanged: () => void;
}

interface CreateDraft {
  client_id?: string;
  service_id?: string;
  plan_id?: string;
  streaming_email?: string;
  streaming_password?: string;
  profile_name?: string;
  profile_pin?: string;
  duration_type?: string;
  starts_at?: string;
  expires_at?: string;
}

function errorCode(error: unknown): string | undefined {
  if (!error || typeof error !== "object") return undefined;
  return "code" in error && typeof error.code === "string"
    ? error.code
    : error instanceof Error
      ? error.message
      : undefined;
}

function errorMessage(error: unknown): string {
  const keys: Record<string, string> = {
    subscription_validation_failed: "frontend.subscriptions.error_validation",
    subscription_invalid_relationship: "frontend.subscriptions.error_relationship",
    subscription_invalid_duration: "frontend.subscriptions.error_duration",
    subscription_pin_requires_profile: "frontend.subscriptions.error_pin_requires_profile",
    subscription_invalid_dates: "frontend.subscriptions.error_dates",
    subscription_duplicate: "frontend.subscriptions.error_duplicate",
    subscription_not_found: "frontend.subscriptions.error_not_found",
    invalid_demo_workspace: "frontend.subscriptions.error_load",
  };
  const code = errorCode(error);
  return code && keys[code]
    ? t(keys[code])
    : t("frontend.demo_simulator.operation_error");
}

function formatDate(value: string): string {
  const date = new Date(value);
  return Number.isNaN(date.getTime())
    ? value
    : new Intl.DateTimeFormat(undefined, { dateStyle: "medium" }).format(date);
}

function normalizeDate(value: string): string {
  const trimmed = value.trim();
  if (/^\d{4}-\d{2}-\d{2}$/.test(trimmed)) return `${trimmed}T00:00:00.000Z`;
  const date = new Date(trimmed);
  if (Number.isNaN(date.getTime())) throw new Error("subscription_invalid_dates");
  return date.toISOString();
}

function totalPages(items: unknown[]): number {
  return Math.max(1, Math.ceil(items.length / PAGE_SIZE));
}

function messageBubbleClass(role: Message["role"]): string {
  return role === "user"
    ? "ml-auto max-w-[90%] rounded-2xl rounded-br-sm bg-primary px-3 py-2 text-primary-foreground"
    : "max-w-[90%] rounded-2xl rounded-bl-sm bg-muted px-3 py-2 text-foreground";
}

function Messages({ messages }: { messages: Message[] }) {
  return (
    <div
      className="flex min-h-[22rem] flex-col gap-3 overflow-y-auto rounded-t-xl bg-background p-4 sm:min-h-[25rem]"
      role="log"
      aria-label={t("frontend.demo_simulator.conversation")}
      aria-live="polite"
    >
      {messages.map((message) => (
        <div key={message.id} className={messageBubbleClass(message.role)}>
          <p className="whitespace-pre-wrap text-sm leading-relaxed">{message.text}</p>
        </div>
      ))}
    </div>
  );
}

export function SubscriptionConsoleExperience({
  onBack,
  onCancel,
  onChanged,
}: SubscriptionConsoleExperienceProps) {
  const { dataSource } = useAuthStore();
  const reducedMotion = usePrefersReducedMotion();
  const mountedRef = useRef(true);
  const [screen, setScreen] = useState<Screen>("menu");
  const [filter, setFilter] = useState<Filter>("all");
  const [page, setPage] = useState(0);
  const [clients, setClients] = useState<Client[]>([]);
  const [services, setServices] = useState<Service[]>([]);
  const [plans, setPlans] = useState<Plan[]>([]);
  const [subscriptions, setSubscriptions] = useState<Subscription[]>([]);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [createDraft, setCreateDraft] = useState<CreateDraft>({});
  const [editPayload, setEditPayload] = useState<SubscriptionUpdate>({});
  const [editField, setEditField] = useState<string | null>(null);
  const [lifecycleDuration, setLifecycleDuration] = useState<string | null>(null);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [loadError, setLoadError] = useState(false);
  const [loadAttempt, setLoadAttempt] = useState(0);
  const [messages, setMessages] = useState<Message[]>([]);
  const selected = subscriptions.find((subscription) => subscription.id === selectedId) ?? null;
  const clientMap = useMemo(() => new Map(clients.map((client) => [client.id, client])), [clients]);
  const serviceMap = useMemo(() => new Map(services.map((service) => [service.id, service])), [services]);
  const planMap = useMemo(() => new Map(plans.map((plan) => [plan.id, plan])), [plans]);

  const loadWorkspace = useCallback(async (cancelled?: () => boolean): Promise<void> => {
    const [nextClients, nextServices, nextSubscriptions] = await Promise.all([
      dataSource.crud.clients.list(),
      dataSource.catalog.listServices(),
      dataSource.subscriptions.list(),
    ]);
    const nextPlans = (await Promise.all(
      nextServices.map((service) => dataSource.catalog.listPlans(service.id)),
    )).flat();
    if (cancelled?.()) return;
    setClients(nextClients);
    setServices(nextServices);
    setPlans(nextPlans);
    setSubscriptions(nextSubscriptions);
  }, [dataSource]);

  useEffect(() => {
    mountedRef.current = true;
    return () => {
      mountedRef.current = false;
    };
  }, []);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setLoadError(false);
    loadWorkspace(() => cancelled)
      .then(() => {
        if (!cancelled) setMessages([{ id: 1, role: "bot", text: menuText() }]);
      })
      .catch(() => {
        if (!cancelled) setLoadError(true);
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [loadWorkspace, loadAttempt]);

  function append(role: Message["role"], text: string) {
    if (!mountedRef.current) return;
    setMessages((current) => [...current, { id: current.length + 1, role, text }]);
  }

  function bot(text: string) {
    append("bot", text);
  }

  function menuText(): string {
    return [
      t("frontend.demo_simulator.subscriptions_menu"),
      `1. ${t("frontend.demo_simulator.subscriptions_view")}`,
      `2. ${t("frontend.demo_simulator.subscriptions_filter")}`,
      `3. ${t("frontend.demo_simulator.subscriptions_create")}`,
      `9. ${t("frontend.demo_simulator.back")}`,
      `0. ${t("frontend.demo_simulator.cancel")}`,
    ].join("\n");
  }

  function filterText(): string {
    return [
      t("frontend.demo_simulator.subscriptions_filter_prompt"),
      `1. ${t("frontend.subscriptions.all_statuses")}`,
      `2. ${t("frontend.subscriptions.status_active")}`,
      `3. ${t("frontend.subscriptions.status_expired")}`,
      `4. ${t("frontend.subscriptions.status_cancelled")}`,
      `9. ${t("frontend.demo_simulator.back")}`,
      `0. ${t("frontend.demo_simulator.cancel")}`,
    ].join("\n");
  }

  function filteredSubscriptions(currentFilter = filter): Subscription[] {
    return subscriptions.filter((subscription) => currentFilter === "all" || subscription.status === currentFilter);
  }

  function listText(nextPage = page, currentFilter = filter): string {
    const records = filteredSubscriptions(currentFilter);
    const pages = totalPages(records);
    const visible = records.slice(nextPage * PAGE_SIZE, (nextPage + 1) * PAGE_SIZE);
    return [
      t("frontend.demo_simulator.subscriptions_select", { page: nextPage + 1, total: pages }),
      ...visible.map((subscription, index) => {
        const client = clientMap.get(subscription.client_id)?.full_name ?? t("frontend.demo_simulator.unknown_client");
        const service = serviceMap.get(subscription.service_id)?.name ?? t("frontend.demo_simulator.unknown_service");
        return t("frontend.demo_simulator.subscription_item", {
          number: index + 1,
          client,
          service,
          email: subscription.streaming_email,
          status: statusLabel(subscription.status),
          expires: formatDate(subscription.expires_at),
        });
      }),
      ...(nextPage < pages - 1 ? [`8. ${t("frontend.demo_simulator.next")}`] : []),
      `9. ${t("frontend.demo_simulator.back")}`,
      `0. ${t("frontend.demo_simulator.cancel")}`,
    ].join("\n");
  }

  function statusLabel(status: string): string {
    if (status === "active") return t("frontend.subscriptions.status_active");
    if (status === "expired") return t("frontend.subscriptions.status_expired");
    return t("frontend.subscriptions.status_cancelled");
  }

  function detailText(subscription: Subscription): string {
    const client = clientMap.get(subscription.client_id)?.full_name ?? t("frontend.demo_simulator.unknown_client");
    const service = serviceMap.get(subscription.service_id)?.name ?? t("frontend.demo_simulator.unknown_service");
    const plan = planMap.get(subscription.plan_id)?.name ?? t("frontend.demo_simulator.unknown_plan");
    const lifecycleAction = subscription.status === "active"
      ? t("frontend.demo_simulator.subscription_cancel_action")
      : t("frontend.demo_simulator.subscription_reactivate_action");
    return [
      t("frontend.demo_simulator.subscription_detail", {
        client,
        service,
        plan,
        email: subscription.streaming_email,
        status: statusLabel(subscription.status),
        starts: formatDate(subscription.starts_at),
        expires: formatDate(subscription.expires_at),
      }),
      "",
      `1. ${t("frontend.demo_simulator.subscription_edit_action")}`,
      `2. ${t("frontend.demo_simulator.subscription_reveal_action")}`,
      `3. ${lifecycleAction}`,
      `4. ${t("frontend.demo_simulator.subscription_renew_action")}`,
      `9. ${t("frontend.demo_simulator.back")}`,
      `0. ${t("frontend.demo_simulator.cancel")}`,
    ].join("\n");
  }

  function clientChoices(): string {
    return [
      t("frontend.demo_simulator.subscription_choose_client"),
      ...clients.map((client, index) => `${index + 1}. ${client.full_name}`),
      `9. ${t("frontend.demo_simulator.back")}`,
      `0. ${t("frontend.demo_simulator.cancel")}`,
    ].join("\n");
  }

  function serviceChoices(): string {
    return [
      t("frontend.demo_simulator.subscription_choose_service"),
      ...services.map((service, index) => `${index + 1}. ${service.name}`),
      `9. ${t("frontend.demo_simulator.back")}`,
      `0. ${t("frontend.demo_simulator.cancel")}`,
    ].join("\n");
  }

  function planChoices(serviceId: string): string {
    const servicePlans = plans.filter((plan) => plan.service_id === serviceId);
    return [
      t("frontend.demo_simulator.subscription_choose_plan"),
      ...servicePlans.map((plan, index) => `${index + 1}. ${plan.name}`),
      `9. ${t("frontend.demo_simulator.back")}`,
      `0. ${t("frontend.demo_simulator.cancel")}`,
    ].join("\n");
  }

  function durationChoices(): string {
    return [
      t("frontend.demo_simulator.subscription_choose_duration"),
      ...DURATION_TYPES.map((duration, index) => `${index + 1}. ${t(`frontend.subscriptions.duration_${duration}`)}`),
      `9. ${t("frontend.demo_simulator.back")}`,
      `0. ${t("frontend.demo_simulator.cancel")}`,
    ].join("\n");
  }

  function editFieldsText(): string {
    return [
      t("frontend.demo_simulator.subscription_edit_fields"),
      `1. ${t("frontend.subscriptions.email")}`,
      `2. ${t("frontend.subscriptions.client")}`,
      `3. ${t("frontend.subscriptions.service")}`,
      `4. ${t("frontend.subscriptions.plan")}`,
      `5. ${t("frontend.subscriptions.duration")}`,
      `6. ${t("frontend.subscriptions.start_date")}`,
      `7. ${t("frontend.subscriptions.end_date")}`,
      `8. ${t("frontend.subscriptions.profile_name")}`,
      `9. ${t("frontend.subscriptions.pin")}`,
      `0. ${t("frontend.demo_simulator.cancel")}`,
    ].join("\n");
  }

  function clearSelection() {
    setSelectedId(null);
    setPage(0);
    setEditPayload({});
    setEditField(null);
  }

  function goMenu() {
    clearSelection();
    setScreen("menu");
    bot(menuText());
  }

  function goList() {
    setScreen("list");
    setPage(0);
    bot(listText(0));
  }

  async function refreshAfterMutation(): Promise<void> {
    await loadWorkspace();
    onChanged();
  }

  async function saveCreate(): Promise<void> {
    if (!createDraft.client_id || !createDraft.service_id || !createDraft.plan_id || !createDraft.streaming_email || !createDraft.duration_type || !createDraft.starts_at) {
      bot(t("frontend.subscriptions.error_validation"));
      return;
    }
    setBusy(true);
    try {
      const created = await dataSource.subscriptions.create(createDraft as SubscriptionCreate);
      setCreateDraft({});
      await refreshAfterMutation();
      setScreen("menu");
      bot(`${t("frontend.demo_simulator.subscription_created", { email: created.streaming_email })}\n\n${menuText()}`);
    } catch (error) {
      bot(`${errorMessage(error)}\n\n${t("frontend.demo_simulator.subscription_create_retry")}`);
    } finally {
      setBusy(false);
    }
  }

  async function saveEdit(payload: SubscriptionUpdate): Promise<void> {
    if (!selectedId) return goMenu();
    setBusy(true);
    try {
      const updated = await dataSource.subscriptions.update(selectedId, payload);
      await refreshAfterMutation();
      setScreen("detail");
      setEditPayload({});
      bot(t("frontend.demo_simulator.subscription_updated", { email: updated.streaming_email }));
      bot(detailText(updated));
    } catch (error) {
      bot(`${errorMessage(error)}\n\n${t("frontend.demo_simulator.subscription_edit_retry")}`);
    } finally {
      setBusy(false);
    }
  }

  async function lifecycle(action: "cancel" | "renew" | "reactivate", duration?: string, expiresAt?: string): Promise<void> {
    if (!selectedId) return goMenu();
    setBusy(true);
    try {
      const updated = action === "cancel"
        ? await dataSource.subscriptions.cancel(selectedId)
        : action === "renew"
          ? await dataSource.subscriptions.renew(selectedId, duration ?? "1_month", expiresAt)
          : await dataSource.subscriptions.reactivate(selectedId, duration ?? "1_month", undefined, expiresAt);
      await refreshAfterMutation();
      setScreen("detail");
      bot(t(`frontend.demo_simulator.subscription_${action === "cancel" ? "cancelled" : action === "renew" ? "renewed" : "reactivated"}`, { email: updated.streaming_email }));
      bot(detailText(updated));
    } catch (error) {
      bot(errorMessage(error));
    } finally {
      setBusy(false);
    }
  }

  async function reveal(): Promise<void> {
    if (!selectedId) return goMenu();
    setBusy(true);
    try {
      const credentials = await dataSource.subscriptions.reveal(selectedId);
      bot(t("frontend.demo_simulator.subscription_revealed", {
        password: credentials.streaming_password ?? t("frontend.subscriptions.no_password"),
        pin: credentials.profile_pin ?? t("frontend.demo_simulator.subscription_no_pin"),
      }));
    } catch (error) {
      bot(errorMessage(error));
    } finally {
      setBusy(false);
    }
  }

  function selectedFrom<T>(items: T[], value: string): T | undefined {
    const index = Number.parseInt(value, 10) - 1;
    return Number.isInteger(index) && index >= 0 ? items[index] : undefined;
  }

  function promptForCreate(screenName: Screen, text: string): void {
    setScreen(screenName);
    bot(text);
  }

  async function handleCreate(text: string): Promise<void> {
    if (screen === "create-client") {
      const client = selectedFrom(clients, text);
      if (!client) return bot(t("frontend.demo_simulator.invalid_navigation"));
      setCreateDraft((current) => ({ ...current, client_id: client.id }));
      promptForCreate("create-service", serviceChoices());
      return;
    }
    if (screen === "create-service") {
      const service = selectedFrom(services, text);
      if (!service) return bot(t("frontend.demo_simulator.invalid_navigation"));
      setCreateDraft((current) => ({ ...current, service_id: service.id }));
      promptForCreate("create-plan", planChoices(service.id));
      return;
    }
    if (screen === "create-plan") {
      const serviceId = createDraft.service_id;
      const plan = serviceId ? selectedFrom(plans.filter((item) => item.service_id === serviceId), text) : undefined;
      if (!plan) return bot(t("frontend.demo_simulator.invalid_navigation"));
      setCreateDraft((current) => ({ ...current, plan_id: plan.id }));
      promptForCreate("create-email", t("frontend.demo_simulator.subscription_email_prompt"));
      return;
    }
    if (screen === "create-email") {
      if (!text.trim()) return bot(t("frontend.subscriptions.error_validation"));
      setCreateDraft((current) => ({ ...current, streaming_email: text.trim() }));
      promptForCreate("create-password", t("frontend.demo_simulator.subscription_password_prompt"));
      return;
    }
    if (screen === "create-password") {
      setCreateDraft((current) => ({ ...current, streaming_password: ["-", "skip", "none"].includes(text.toLowerCase()) ? undefined : text }));
      promptForCreate("create-profile", t("frontend.demo_simulator.subscription_profile_prompt"));
      return;
    }
    if (screen === "create-profile") {
      setCreateDraft((current) => ({ ...current, profile_name: ["-", "skip", "none"].includes(text.toLowerCase()) ? undefined : text }));
      promptForCreate("create-pin", t("frontend.demo_simulator.subscription_pin_prompt"));
      return;
    }
    if (screen === "create-pin") {
      setCreateDraft((current) => ({ ...current, profile_pin: ["-", "skip", "none"].includes(text.toLowerCase()) ? undefined : text }));
      promptForCreate("create-duration", durationChoices());
      return;
    }
    if (screen === "create-duration") {
      const duration = DURATION_TYPES[Number.parseInt(text, 10) - 1];
      if (!duration) return bot(t("frontend.demo_simulator.invalid_navigation"));
      setCreateDraft((current) => ({ ...current, duration_type: duration }));
      promptForCreate("create-start", t("frontend.demo_simulator.subscription_start_prompt"));
      return;
    }
    if (screen === "create-start") {
      try {
        const startsAt = normalizeDate(text);
        setCreateDraft((current) => ({ ...current, starts_at: startsAt }));
        if (createDraft.duration_type === "custom") promptForCreate("create-expiry", t("frontend.demo_simulator.subscription_expiry_prompt"));
        else promptForCreate("create-confirm", t("frontend.demo_simulator.subscription_create_confirm"));
      } catch (error) {
        bot(errorMessage(error));
      }
      return;
    }
    if (screen === "create-expiry") {
      try {
        const expiresAt = normalizeDate(text);
        setCreateDraft((current) => ({ ...current, expires_at: expiresAt }));
        promptForCreate("create-confirm", t("frontend.demo_simulator.subscription_create_confirm"));
      } catch (error) {
        bot(errorMessage(error));
      }
      return;
    }
    if (screen === "create-confirm") {
      if (!/^confirm(ar)?$/i.test(text)) return bot(t("frontend.demo_simulator.confirm_reprompt"));
      await saveCreate();
    }
  }

  async function handleEdit(text: string): Promise<void> {
    if (!selected) return goMenu();
    if (screen === "edit-fields") {
      const prompts: Record<string, [string, string]> = {
        "1": ["streaming_email", t("frontend.demo_simulator.subscription_email_prompt")],
        "5": ["duration_type", durationChoices()],
        "6": ["starts_at", t("frontend.demo_simulator.subscription_start_prompt")],
        "7": ["expires_at", t("frontend.demo_simulator.subscription_expiry_prompt")],
        "8": ["profile_name", t("frontend.demo_simulator.subscription_profile_prompt")],
        "9": ["profile_pin", t("frontend.demo_simulator.subscription_pin_prompt")],
      };
      if (text === "2") return promptForCreate("edit-client", clientChoices());
      if (text === "3") return promptForCreate("edit-service", serviceChoices());
      if (text === "4") return promptForCreate("edit-plan", planChoices(selected.service_id));
      if (text === "5") {
        setScreen("edit-duration");
        return bot(durationChoices());
      }
      const prompt = prompts[text];
      if (!prompt) return bot(t("frontend.demo_simulator.invalid_navigation"));
      setEditField(prompt[0]);
      setScreen("edit-value");
      bot(prompt[1]);
      return;
    }
    if (screen === "edit-client") {
      const client = selectedFrom(clients, text);
      if (!client) return bot(t("frontend.demo_simulator.invalid_navigation"));
      await saveEdit({ client_id: client.id });
      return;
    }
    if (screen === "edit-service") {
      const service = selectedFrom(services, text);
      if (!service) return bot(t("frontend.demo_simulator.invalid_navigation"));
      setEditPayload({ service_id: service.id });
      setScreen("edit-service-plan");
      bot(planChoices(service.id));
      return;
    }
    if (screen === "edit-service-plan") {
      const serviceId = editPayload.service_id;
      const plan = serviceId ? selectedFrom(plans.filter((item) => item.service_id === serviceId), text) : undefined;
      if (!plan) return bot(t("frontend.demo_simulator.invalid_navigation"));
      await saveEdit({ service_id: serviceId, plan_id: plan.id });
      return;
    }
    if (screen === "edit-plan") {
      const plan = selectedFrom(plans.filter((item) => item.service_id === selected.service_id), text);
      if (!plan) return bot(t("frontend.demo_simulator.invalid_navigation"));
      await saveEdit({ plan_id: plan.id });
      return;
    }
    if (screen === "edit-duration") {
      const duration = DURATION_TYPES[Number.parseInt(text, 10) - 1];
      if (!duration) return bot(t("frontend.demo_simulator.invalid_navigation"));
      if (duration === "custom") {
        setScreen("edit-duration-expiry");
        return bot(t("frontend.demo_simulator.subscription_expiry_prompt"));
      }
      await saveEdit({ duration_type: duration });
      return;
    }
    if (screen === "edit-duration-expiry") {
      try {
        await saveEdit({ duration_type: "custom", expires_at: normalizeDate(text) });
      } catch (error) {
        bot(errorMessage(error));
      }
      return;
    }
    if (screen === "edit-value") {
      if (!editField) return goMenu();
      try {
        const value = editField.endsWith("_at") ? normalizeDate(text) : ["-", "skip", "none"].includes(text.toLowerCase()) ? "" : text;
        await saveEdit({ [editField]: value });
      } catch (error) {
        bot(errorMessage(error));
      }
    }
  }

  async function handleText(text: string): Promise<void> {
    if (screen === "menu") {
      if (text === "1") return goList();
      if (text === "2") {
        setScreen("filter");
        return bot(filterText());
      }
      if (text === "3") {
        setCreateDraft({});
        return promptForCreate("create-client", clientChoices());
      }
      return bot(t("frontend.demo_simulator.invalid_navigation"));
    }
    if (screen === "filter") {
      const nextFilter: Filter | undefined = { "1": "all", "2": "active", "3": "expired", "4": "cancelled" }[text] as Filter | undefined;
      if (!nextFilter) return bot(t("frontend.demo_simulator.invalid_navigation"));
      setFilter(nextFilter);
      setPage(0);
      setScreen("list");
      bot(listText(0, nextFilter));
      return;
    }
    if (screen === "list") {
      const records = filteredSubscriptions();
      if (text === "8") {
        const lastPage = totalPages(records) - 1;
        if (page >= lastPage) return bot(t("frontend.demo_simulator.no_next_page"));
        const next = page + 1;
        setPage(next);
        return bot(listText(next));
      }
      const record = selectedFrom(records.slice(page * PAGE_SIZE, (page + 1) * PAGE_SIZE), text);
      if (!record) return bot(t("frontend.demo_simulator.invalid_navigation"));
      setSelectedId(record.id);
      setScreen("detail");
      bot(detailText(record));
      return;
    }
    if (screen === "detail") {
      if (!selected) return goMenu();
      if (text === "1") {
        setScreen("edit-fields");
        return bot(editFieldsText());
      }
      if (text === "2") return reveal();
      if (text === "3") {
        if (selected.status === "active") {
          setScreen("cancel-confirm");
          return bot(t("frontend.demo_simulator.subscription_cancel_confirm", { email: selected.streaming_email }));
        }
        setScreen("reactivate-duration");
        return bot(durationChoices());
      }
      if (text === "4") {
        setScreen("renew-duration");
        return bot(durationChoices());
      }
      return bot(t("frontend.demo_simulator.invalid_navigation"));
    }
    if (screen === "cancel-confirm") {
      if (!/^confirm(ar)?$/i.test(text)) return bot(t("frontend.demo_simulator.confirm_reprompt"));
      await lifecycle("cancel");
      return;
    }
    if (screen === "renew-duration" || screen === "reactivate-duration") {
      const duration = DURATION_TYPES[Number.parseInt(text, 10) - 1];
      if (!duration) return bot(t("frontend.demo_simulator.invalid_navigation"));
      const action = screen === "renew-duration" ? "renew" : "reactivate";
      if (duration === "custom") {
        setLifecycleDuration(duration);
        setScreen(action === "renew" ? "renew-expiry" : "reactivate-expiry");
        bot(t("frontend.demo_simulator.subscription_expiry_prompt"));
        return;
      }
      await lifecycle(action, duration);
      return;
    }
    if (screen === "renew-expiry" || screen === "reactivate-expiry") {
      try {
        const expiresAt = normalizeDate(text);
        const action = screen === "renew-expiry" ? "renew" : "reactivate";
        await lifecycle(action, lifecycleDuration ?? "custom", expiresAt);
      } catch (error) {
        bot(errorMessage(error));
      }
      return;
    }
    if (screen === "edit-fields" || screen === "edit-value" || screen === "edit-duration" || screen === "edit-duration-expiry" || screen === "edit-client" || screen === "edit-service" || screen === "edit-plan" || screen === "edit-service-plan") {
      await handleEdit(text);
      return;
    }
    await handleCreate(text);
  }

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const text = input.trim();
    if (!text || busy || loading) return;
    append("user", text);
    setInput("");
    if (text === "0") return onCancel();
    if (text === "9") {
      if (screen === "menu") return onBack();
      if (screen === "list" || screen === "filter") return goMenu();
      if (screen === "detail") return goList();
      if (screen.startsWith("create-")) return goMenu();
      if (screen.startsWith("edit-")) {
        if (selected) {
          setScreen("detail");
          bot(detailText(selected));
        } else goMenu();
        return;
      }
    }
    void handleText(text);
  }

  if (loading) {
    return (
      <div className="flex min-h-[22rem] items-center justify-center text-sm text-muted-foreground" role="status">
        <Loader2 className={`mr-2 size-4 ${reducedMotion ? "" : "animate-spin"}`} aria-hidden="true" />
        {t("frontend.demo_simulator.client_loading")}
      </div>
    );
  }
  if (loadError) {
    return (
      <Alert variant="destructive">
        <AlertTitle>{t("frontend.demo_simulator.operation_error")}</AlertTitle>
        <AlertDescription className="flex flex-col gap-3">
          <span>{t("frontend.subscriptions.error_load")}</span>
          <Button type="button" variant="outline" onClick={() => setLoadAttempt((attempt) => attempt + 1)}>
            {t("frontend.demo_simulator.retry")}
          </Button>
        </AlertDescription>
      </Alert>
    );
  }

  return (
    <Card className="mx-auto w-full max-w-md overflow-hidden">
      <CardHeader className="border-b bg-muted/30">
        <CardTitle>{t("frontend.demo_simulator.subscriptions_title")}</CardTitle>
        <CardDescription>{t("frontend.demo_simulator.local_operation_description")}</CardDescription>
      </CardHeader>
      <CardContent className="p-0">
        <Messages messages={messages} />
        <form className="flex gap-2 border-t bg-muted/30 p-3" onSubmit={handleSubmit}>
          <label className="sr-only" htmlFor="subscription-console-input">{t("frontend.demo_simulator.message_input_label")}</label>
          <Input
            id="subscription-console-input"
            value={input}
            onChange={(event) => setInput(event.target.value)}
            placeholder={t("frontend.demo_simulator.operation_placeholder")}
            autoComplete="off"
            autoFocus
            disabled={busy}
          />
          <Button type="submit" size="icon" aria-label={t("frontend.demo_simulator.send")} disabled={!input.trim() || busy}>
            <Send className="size-4" aria-hidden="true" />
          </Button>
        </form>
      </CardContent>
    </Card>
  );
}
