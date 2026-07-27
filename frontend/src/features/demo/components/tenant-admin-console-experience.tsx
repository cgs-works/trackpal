import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import type { FormEvent } from "react";
import { Loader2, Send } from "lucide-react";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { t } from "@/i18n";
import type { Client } from "@/features/admin/services/client-api";
import type { DeletePreview, Plan, Service } from "@/features/admin/services/catalog-api";
import { useAuthStore } from "@/store/auth";
import { useCatalogStore } from "@/store/catalog";
import { usePrefersReducedMotion } from "./use-prefers-reduced-motion";

const PAGE_SIZE = 4;

type Section = "clients" | "catalog";
type Screen =
  | "menu"
  | "client-select"
  | "client-detail"
  | "client-edit-field"
  | "client-edit-value"
  | "client-create-name"
  | "client-create-phone"
  | "client-create-username"
  | "client-create-password"
  | "client-create-confirm"
  | "client-confirm"
  | "service-select"
  | "service-detail"
  | "service-create-name"
  | "service-edit-name"
  | "service-delete-select"
  | "service-delete-confirm"
  | "plan-select"
  | "plan-detail"
  | "plan-create-name"
  | "plan-edit-name"
  | "plan-delete-select"
  | "plan-delete-confirm";

type Confirmation = "client-deactivate" | "client-delete" | "service-delete" | "plan-delete";

type Message = { id: number; role: "bot" | "user"; text: string };

type ClientDraft = {
  fullName: string;
  phone?: string;
  localUsername: string;
  password: string;
};

interface TenantAdminConsoleExperienceProps {
  section: Section;
  onBack: () => void;
  onCancel: () => void;
  onChanged: () => void;
}

function errorCode(error: unknown): string | undefined {
  if (!error || typeof error !== "object") return undefined;
  if ("code" in error && typeof error.code === "string") return error.code;
  return error instanceof Error ? error.message : undefined;
}

function errorMessage(error: unknown): string {
  const code = errorCode(error);
  const keys: Record<string, string> = {
    client_local_username_exists: "frontend.demo_simulator.client_error_username",
    phone_already_registered: "frontend.demo_simulator.client_error_phone",
    client_delete_active: "frontend.demo_simulator.client_error_active",
    client_has_subscriptions: "frontend.demo_simulator.client_error_subscriptions",
    client_validation_failed: "frontend.demo_simulator.client_error_validation",
    client_not_found: "frontend.demo_simulator.client_error_not_found",
    service_name_already_exists: "frontend.demo_simulator.catalog_error_duplicate",
    plan_name_already_exists: "frontend.demo_simulator.catalog_error_duplicate",
    catalog_name_required: "frontend.demo_simulator.catalog_error_name",
    catalog_name_too_long: "frontend.demo_simulator.catalog_error_name",
    service_not_found: "frontend.demo_simulator.catalog_error_not_found",
    plan_not_found: "frontend.demo_simulator.catalog_error_not_found",
    invalid_demo_workspace: "frontend.demo_simulator.workspace_error",
  };
  return code && keys[code]
    ? t(keys[code])
    : t("frontend.demo_simulator.operation_error");
}

function totalPages(items: unknown[]): number {
  return Math.max(1, Math.ceil(items.length / PAGE_SIZE));
}

function messageBubbleClass(role: Message["role"]): string {
  return role === "user"
    ? "ml-auto max-w-[90%] rounded-2xl rounded-br-sm bg-primary px-3 py-2 text-primary-foreground"
    : "max-w-[90%] rounded-2xl rounded-bl-sm bg-muted px-3 py-2 text-foreground";
}

function TenantAdminMessages({ messages }: { messages: Message[] }) {
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

export function TenantAdminConsoleExperience({
  section,
  onBack,
  onCancel,
  onChanged,
}: TenantAdminConsoleExperienceProps) {
  const { dataSource } = useAuthStore();
  const reducedMotion = usePrefersReducedMotion();
  const mountedRef = useRef(true);
  const [screen, setScreen] = useState<Screen>("menu");
  const [page, setPage] = useState(0);
  const [clients, setClients] = useState<Client[]>([]);
  const [services, setServices] = useState<Service[]>([]);
  const [plans, setPlans] = useState<Plan[]>([]);
  const [selectedClientId, setSelectedClientId] = useState<string | null>(null);
  const [selectedServiceId, setSelectedServiceId] = useState<string | null>(null);
  const [selectedPlanId, setSelectedPlanId] = useState<string | null>(null);
  const [preview, setPreview] = useState<DeletePreview | null>(null);
  const [confirmation, setConfirmation] = useState<Confirmation | null>(null);
  const [draft, setDraft] = useState<ClientDraft>({ fullName: "", localUsername: "", password: "" });
  const [editField, setEditField] = useState<"full_name" | "phone" | "local_username" | null>(null);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [loadError, setLoadError] = useState(false);
  const [loadAttempt, setLoadAttempt] = useState(0);
  const [messages, setMessages] = useState<Message[]>([]);

  const copy = useMemo(() => ({
    clientsMenu: t("frontend.demo_simulator.clients_menu"),
    catalogMenu: t("frontend.demo_simulator.catalog_menu"),
  }), []);

  function append(role: Message["role"], text: string) {
    if (!mountedRef.current) return;
    setMessages((current) => [
      ...current,
      { id: current.length + 1, role, text },
    ]);
  }

  function bot(text: string) {
    append("bot", text);
  }

  const loadWorkspace = useCallback(async (cancelled?: () => boolean): Promise<void> => {
    if (section === "clients") {
      const nextClients = await dataSource.crud.clients.list();
      if (cancelled?.()) return;
      setClients(nextClients);
      return;
    }
    const nextServices = await dataSource.catalog.listServices();
    const nextPlans = (await Promise.all(
      nextServices.map((service) => dataSource.catalog.listPlans(service.id)),
    )).flat();
    if (cancelled?.()) return;
    setServices(nextServices);
    setPlans(nextPlans);
  }, [dataSource, section]);

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
        if (cancelled) return;
        setMessages([{ id: 1, role: "bot", text: section === "clients" ? copy.clientsMenu : copy.catalogMenu }]);
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
  }, [copy.catalogMenu, copy.clientsMenu, loadAttempt, loadWorkspace, section]);

  function invalidateWorkspaceCaches() {
    const catalog = useCatalogStore.getState();
    if (section === "clients") catalog.invalidateClients();
    else catalog.invalidateServices();
    catalog.invalidatePlans();
    onChanged();
  }

  async function refreshAfterMutation(): Promise<void> {
    invalidateWorkspaceCaches();
    await loadWorkspace();
  }

  function menuText(): string {
    return section === "clients"
      ? `${copy.clientsMenu}\n\n1. ${t("frontend.demo_simulator.clients_view")}\n2. ${t("frontend.demo_simulator.clients_create")}\n\n9. ${t("frontend.demo_simulator.back")}\n0. ${t("frontend.demo_simulator.cancel")}`
      : `${copy.catalogMenu}\n\n1. ${t("frontend.demo_simulator.catalog_view")}\n2. ${t("frontend.demo_simulator.catalog_create_service")}\n3. ${t("frontend.demo_simulator.catalog_delete_service")}\n\n9. ${t("frontend.demo_simulator.back")}\n0. ${t("frontend.demo_simulator.cancel")}`;
  }

  function clientListText(nextPage = page): string {
    const total = totalPages(clients);
    const visible = clients.slice(nextPage * PAGE_SIZE, (nextPage + 1) * PAGE_SIZE);
    return [
      t("frontend.demo_simulator.clients_select", { page: nextPage + 1, total }),
      ...visible.map((client, index) => t("frontend.demo_simulator.clients_item", {
        number: index + 1,
        name: client.full_name,
        status: client.is_active
          ? t("frontend.demo_simulator.client_active")
          : t("frontend.demo_simulator.client_inactive"),
      })),
      ...(nextPage < total - 1 ? [`8. ${t("frontend.demo_simulator.next")}`] : []),
      `9. ${t("frontend.demo_simulator.back")}`,
      `0. ${t("frontend.demo_simulator.cancel")}`,
    ].join("\n");
  }

  function serviceListText(nextPage = page, deleting = false): string {
    const total = totalPages(services);
    const visible = services.slice(nextPage * PAGE_SIZE, (nextPage + 1) * PAGE_SIZE);
    return [
      t("frontend.demo_simulator.services_select", { page: nextPage + 1, total }),
      ...visible.map((service, index) => t("frontend.demo_simulator.services_item", {
        number: index + 1,
        name: service.name,
        count: plans.filter((plan) => plan.service_id === service.id).length,
      })),
      ...(nextPage < total - 1 ? [`8. ${t("frontend.demo_simulator.next")}`] : []),
      `9. ${t("frontend.demo_simulator.back")}`,
      `0. ${t("frontend.demo_simulator.cancel")}`,
      ...(deleting ? [`\n${t("frontend.demo_simulator.catalog_delete_hint")}`] : []),
    ].join("\n");
  }

  function planListText(serviceId: string, nextPage = page, deleting = false): string {
    const servicePlans = plans.filter((plan) => plan.service_id === serviceId);
    const total = totalPages(servicePlans);
    const visible = servicePlans.slice(nextPage * PAGE_SIZE, (nextPage + 1) * PAGE_SIZE);
    return [
      t("frontend.demo_simulator.plans_select", { page: nextPage + 1, total }),
      ...visible.map((plan, index) => `${index + 1}. ${plan.name}`),
      ...(nextPage < total - 1 ? [`8. ${t("frontend.demo_simulator.next")}`] : []),
      `9. ${t("frontend.demo_simulator.back")}`,
      `0. ${t("frontend.demo_simulator.cancel")}`,
      ...(deleting ? [`\n${t("frontend.demo_simulator.catalog_delete_hint")}`] : []),
    ].join("\n");
  }

  function selectedClient(): Client | null {
    return clients.find((client) => client.id === selectedClientId) ?? null;
  }

  function selectedService(): Service | null {
    return services.find((service) => service.id === selectedServiceId) ?? null;
  }

  function selectedPlan(): Plan | null {
    return plans.find((plan) => plan.id === selectedPlanId) ?? null;
  }

  function clientDetailText(client: Client): string {
    return `${t("frontend.demo_simulator.client_detail", {
      name: client.full_name,
      username: client.username,
      phone: client.phone ?? t("frontend.demo_simulator.client_phone_missing"),
      status: client.is_active
        ? t("frontend.demo_simulator.client_active")
        : t("frontend.demo_simulator.client_inactive"),
    })}\n\n${client.is_active
      ? t("frontend.demo_simulator.client_actions_active")
      : t("frontend.demo_simulator.client_actions_inactive")}`;
  }

  function serviceDetailText(service: Service): string {
    const servicePlans = plans.filter((plan) => plan.service_id === service.id);
    return `${t("frontend.demo_simulator.service_detail", {
      name: service.name,
      plans: servicePlans.length,
    })}\n\n${t("frontend.demo_simulator.service_actions")}`;
  }

  function planDetailText(plan: Plan): string {
    return `${t("frontend.demo_simulator.plan_detail", { name: plan.name })}\n\n${t("frontend.demo_simulator.plan_actions")}`;
  }

  function goMenu() {
    setScreen("menu");
    setPage(0);
    setSelectedClientId(null);
    setSelectedServiceId(null);
    setSelectedPlanId(null);
    setConfirmation(null);
    setPreview(null);
    bot(menuText());
  }

  function goBack() {
    if (screen === "menu") return onBack();
    if (screen === "client-select") {
      if (page > 0) {
        setPage((current) => current - 1);
        bot(clientListText(page - 1));
      } else goMenu();
      return;
    }
    if (screen === "client-detail") {
      setScreen("client-select");
      setPage(0);
      bot(clientListText(0));
      return;
    }
    if (screen === "client-edit-field") {
      const client = selectedClient();
      if (client) {
        setScreen("client-detail");
        bot(clientDetailText(client));
      } else goMenu();
      return;
    }
    if (screen === "client-edit-value") {
      setScreen("client-edit-field");
      bot(t("frontend.demo_simulator.client_edit_fields"));
      return;
    }
    if (screen.startsWith("client-create")) {
      const previous: Record<string, Screen> = {
        "client-create-name": "menu",
        "client-create-phone": "client-create-name",
        "client-create-username": "client-create-phone",
        "client-create-password": "client-create-username",
        "client-create-confirm": "client-create-password",
      };
      const next = previous[screen];
      if (next === "menu") goMenu();
      else {
        setScreen(next);
        bot(t(`frontend.demo_simulator.${next.replaceAll("-", "_")}_prompt`));
      }
      return;
    }
    if (screen === "client-confirm") {
      setConfirmation(null);
      const client = selectedClient();
      if (client) {
        setScreen("client-detail");
        bot(clientDetailText(client));
      } else goMenu();
      return;
    }
    if (screen === "service-select" || screen === "service-delete-select") {
      if (page > 0) {
        setPage((current) => current - 1);
        bot(serviceListText(page - 1, screen === "service-delete-select"));
      } else goMenu();
      return;
    }
    if (screen === "service-detail") {
      setScreen("service-select");
      setPage(0);
      bot(serviceListText(0));
      return;
    }
    if (screen === "service-edit-name" || screen === "plan-select" || screen === "service-delete-confirm") {
      const service = selectedService();
      if (service) {
        setScreen("service-detail");
        setPreview(null);
        setConfirmation(null);
        bot(serviceDetailText(service));
      } else goMenu();
      return;
    }
    if (screen === "plan-detail") {
      const service = selectedService();
      if (service) {
        setScreen("plan-select");
        setPage(0);
        bot(planListText(service.id));
      } else goMenu();
      return;
    }
    if (screen === "plan-edit-name" || screen === "plan-delete-confirm") {
      const plan = selectedPlan();
      if (plan) {
        setScreen("plan-detail");
        setPreview(null);
        setConfirmation(null);
        bot(planDetailText(plan));
      } else goMenu();
      return;
    }
    if (screen === "plan-delete-select") {
      const service = selectedService();
      if (service) {
        setScreen("service-detail");
        bot(serviceDetailText(service));
      } else goMenu();
      return;
    }
    if (screen === "service-create-name" || screen === "plan-create-name") {
      const service = selectedService();
      if (screen === "plan-create-name" && service) {
        setScreen("service-detail");
        bot(serviceDetailText(service));
      } else goMenu();
    }
  }

  async function completeMutation(success: string) {
    await refreshAfterMutation();
    if (!mountedRef.current) return;
    setScreen("menu");
    setPage(0);
    setSelectedClientId(null);
    setSelectedServiceId(null);
    setSelectedPlanId(null);
    setConfirmation(null);
    setPreview(null);
    bot(`${success}\n\n${menuText()}`);
  }

  async function handleClientMessage(text: string): Promise<void> {
    if (screen === "menu") {
      if (text === "1") {
        setScreen("client-select");
        setPage(0);
        bot(clients.length > 0 ? clientListText(0) : t("frontend.demo_simulator.clients_empty"));
      } else if (text === "2") {
        setScreen("client-create-name");
        bot(t("frontend.demo_simulator.client_create_name_prompt"));
      } else bot(t("frontend.demo_simulator.invalid_navigation"));
      return;
    }
    if (screen === "client-select") {
      if (text === "8") {
        const last = totalPages(clients) - 1;
        if (page >= last) bot(t("frontend.demo_simulator.no_next_page"));
        else {
          const next = page + 1;
          setPage(next);
          bot(clientListText(next));
        }
        return;
      }
      const selection = Number.parseInt(text, 10);
      const client = Number.isInteger(selection) && selection > 0
        ? clients[page * PAGE_SIZE + selection - 1]
        : undefined;
      if (!client) bot(t("frontend.demo_simulator.invalid_navigation"));
      else {
        setSelectedClientId(client.id);
        setScreen("client-detail");
        setPage(0);
        bot(clientDetailText(client));
      }
      return;
    }
    if (screen === "client-detail") {
      const client = selectedClient();
      if (!client) return goMenu();
      if (text === "1") {
        setScreen("client-edit-field");
        bot(t("frontend.demo_simulator.client_edit_fields"));
      } else if (text === "2" && client.is_active) {
        setConfirmation("client-deactivate");
        setScreen("client-confirm");
        bot(t("frontend.demo_simulator.client_deactivate_confirm", { name: client.full_name }));
      } else if (text === "2") {
        setBusy(true);
        try {
          const updated = await dataSource.crud.clients.activate(client.id);
          await completeMutation(t("frontend.demo_simulator.client_activated", { name: updated.full_name }));
        } catch (error) {
          bot(errorMessage(error));
        } finally {
          setBusy(false);
        }
      } else if (text === "3" && client.is_active) {
        bot(t("frontend.demo_simulator.client_error_active"));
      } else if (text === "3") {
        setBusy(true);
        try {
          const nextPreview = await dataSource.crud.clients.getDeletePreview(client.id);
          setPreview(nextPreview);
          setConfirmation("client-delete");
          setScreen("client-confirm");
          bot(t("frontend.demo_simulator.client_delete_confirm", {
            name: client.full_name,
            active: nextPreview.active_subscription_count,
            historical: nextPreview.historical_subscription_count,
          }));
        } catch (error) {
          bot(errorMessage(error));
        } finally {
          setBusy(false);
        }
      } else bot(t("frontend.demo_simulator.invalid_navigation"));
      return;
    }
    if (screen === "client-edit-field") {
      const fields: Record<string, [typeof editField, string]> = {
        "1": ["full_name", t("frontend.demo_simulator.client_edit_name_prompt")],
        "2": ["phone", t("frontend.demo_simulator.client_edit_phone_prompt")],
        "3": ["local_username", t("frontend.demo_simulator.client_edit_username_prompt")],
      };
      const field = fields[text];
      if (!field) bot(t("frontend.demo_simulator.invalid_navigation"));
      else {
        setEditField(field[0]);
        setScreen("client-edit-value");
        bot(field[1]);
      }
      return;
    }
    if (screen === "client-edit-value") {
      if (!editField || !selectedClientId) return goMenu();
      setBusy(true);
      try {
        let payload;
        if (editField === "full_name") {
          payload = { full_name: text };
        } else if (editField === "local_username") {
          payload = { local_username: text.toLowerCase() };
        } else {
          payload = { phone: text === "—" ? undefined : text };
        }
        const updated = await dataSource.crud.clients.update(selectedClientId, payload);
        await completeMutation(t("frontend.demo_simulator.client_updated", { name: updated.full_name }));
      } catch (error) {
        bot(`${errorMessage(error)}\n\n${t(`frontend.demo_simulator.client_edit_${editField}_prompt`)}`);
      } finally {
        setBusy(false);
      }
      return;
    }
    if (screen === "client-create-name") {
      if (!text.trim()) bot(t("frontend.demo_simulator.client_error_name"));
      else {
        setDraft((current) => ({ ...current, fullName: text }));
        setScreen("client-create-phone");
        bot(t("frontend.demo_simulator.client_create_phone_prompt"));
      }
      return;
    }
    if (screen === "client-create-phone") {
      setDraft((current) => ({ ...current, phone: ["—", "-", "skip", "none"].includes(text.toLowerCase()) ? undefined : text }));
      setScreen("client-create-username");
      bot(t("frontend.demo_simulator.client_create_username_prompt"));
      return;
    }
    if (screen === "client-create-username") {
      if (!text.trim()) bot(t("frontend.demo_simulator.client_error_username"));
      else {
        setDraft((current) => ({ ...current, localUsername: text.toLowerCase() }));
        setScreen("client-create-password");
        bot(t("frontend.demo_simulator.client_create_password_prompt"));
      }
      return;
    }
    if (screen === "client-create-password") {
      if (text.length < 6) bot(t("frontend.demo_simulator.client_error_password"));
      else {
        const nextDraft = { ...draft, password: text };
        setDraft(nextDraft);
        setScreen("client-create-confirm");
        bot(t("frontend.demo_simulator.client_create_confirm", {
          name: nextDraft.fullName,
          username: nextDraft.localUsername,
          phone: nextDraft.phone ?? t("frontend.demo_simulator.client_phone_missing"),
        }));
      }
      return;
    }
    if (screen === "client-create-confirm") {
      if (!/^confirm(ar)?$/i.test(text)) {
        bot(t("frontend.demo_simulator.confirm_reprompt"));
        return;
      }
      setBusy(true);
      try {
        const created = await dataSource.crud.clients.create({
          full_name: draft.fullName,
          local_username: draft.localUsername,
          phone: draft.phone,
          password: draft.password,
        });
        await completeMutation(t("frontend.demo_simulator.client_created", { name: created.full_name }));
      } catch (error) {
        const code = errorCode(error);
        if (code === "phone_already_registered" || (code === "client_validation_failed" && error instanceof Error && error.message.includes("phone"))) {
          setScreen("client-create-phone");
          bot(`${errorMessage(error)}\n\n${t("frontend.demo_simulator.client_create_phone_prompt")}`);
        } else if (code === "client_local_username_exists" || (code === "client_validation_failed" && error instanceof Error && error.message.includes("username"))) {
          setScreen("client-create-username");
          bot(`${errorMessage(error)}\n\n${t("frontend.demo_simulator.client_create_username_prompt")}`);
        } else if (code === "client_validation_failed" && error instanceof Error && error.message.includes("password")) {
          setScreen("client-create-password");
          bot(`${errorMessage(error)}\n\n${t("frontend.demo_simulator.client_create_password_prompt")}`);
        } else if (code === "client_validation_failed" && error instanceof Error && error.message.includes("full_name")) {
          setScreen("client-create-name");
          bot(`${errorMessage(error)}\n\n${t("frontend.demo_simulator.client_create_name_prompt")}`);
        } else {
          bot(errorMessage(error));
        }
      } finally {
        setBusy(false);
      }
      return;
    }
    if (screen === "client-confirm") {
      if (!/^confirm(ar)?$/i.test(text) || !confirmation || !selectedClientId) {
        bot(t("frontend.demo_simulator.confirm_reprompt"));
        return;
      }
      setBusy(true);
      try {
        if (confirmation === "client-deactivate") {
          const updated = await dataSource.crud.clients.deactivate(selectedClientId);
          await completeMutation(t("frontend.demo_simulator.client_deactivated", { name: updated.full_name }));
        } else {
          const client = selectedClient();
          await dataSource.crud.clients.delete(selectedClientId);
          await completeMutation(t("frontend.demo_simulator.client_deleted", { name: client?.full_name ?? "" }));
        }
      } catch (error) {
        bot(errorMessage(error));
      } finally {
        setBusy(false);
      }
    }
  }

  async function handleCatalogMessage(text: string): Promise<void> {
    if (screen === "menu") {
      if (text === "1") {
        setScreen("service-select");
        setPage(0);
        bot(services.length > 0 ? serviceListText(0) : t("frontend.demo_simulator.catalog_empty"));
      } else if (text === "2") {
        setScreen("service-create-name");
        bot(t("frontend.demo_simulator.catalog_create_service_prompt"));
      } else if (text === "3") {
        if (!services.length) bot(t("frontend.demo_simulator.catalog_empty"));
        else {
          setScreen("service-delete-select");
          setPage(0);
          bot(serviceListText(0, true));
        }
      } else bot(t("frontend.demo_simulator.invalid_navigation"));
      return;
    }
    if (screen === "service-select" || screen === "service-delete-select") {
      if (text === "8") {
        const last = totalPages(services) - 1;
        if (page >= last) bot(t("frontend.demo_simulator.no_next_page"));
        else {
          const next = page + 1;
          setPage(next);
          bot(serviceListText(next, screen === "service-delete-select"));
        }
        return;
      }
      const selection = Number.parseInt(text, 10);
      const service = Number.isInteger(selection) && selection > 0
        ? services[page * PAGE_SIZE + selection - 1]
        : undefined;
      if (!service) bot(t("frontend.demo_simulator.invalid_navigation"));
      else {
        setSelectedServiceId(service.id);
        setPage(0);
        if (screen === "service-delete-select") {
          setBusy(true);
          try {
            const nextPreview = await dataSource.catalog.getServiceDeletePreview(service.id);
            setPreview(nextPreview);
            setConfirmation("service-delete");
            setScreen("service-delete-confirm");
            bot(t("frontend.demo_simulator.catalog_delete_confirm", {
              type: t("frontend.demo_simulator.service"),
              name: nextPreview.target_name,
              plans: nextPreview.affected_plan_count,
              active: nextPreview.active_subscription_count,
              historical: nextPreview.historical_subscription_count,
            }));
          } catch (error) {
            bot(errorMessage(error));
          } finally {
            setBusy(false);
          }
        } else {
          setScreen("service-detail");
          bot(serviceDetailText(service));
        }
      }
      return;
    }
    if (screen === "service-detail") {
      const service = selectedService();
      if (!service) return goMenu();
      if (text === "1") {
        setScreen("service-edit-name");
        bot(t("frontend.demo_simulator.catalog_edit_service_prompt"));
      } else if (text === "2") {
        const servicePlans = plans.filter((plan) => plan.service_id === service.id);
        if (!servicePlans.length) bot(t("frontend.demo_simulator.catalog_no_plans"));
        else {
          setScreen("plan-select");
          setPage(0);
          bot(planListText(service.id));
        }
      } else if (text === "3") {
        setScreen("plan-create-name");
        bot(t("frontend.demo_simulator.catalog_create_plan_prompt"));
      } else if (text === "4") {
        const servicePlans = plans.filter((plan) => plan.service_id === service.id);
        if (!servicePlans.length) bot(t("frontend.demo_simulator.catalog_no_plans_delete"));
        else {
          setScreen("plan-delete-select");
          setPage(0);
          bot(planListText(service.id, 0, true));
        }
      } else bot(t("frontend.demo_simulator.invalid_navigation"));
      return;
    }
    if (screen === "service-create-name") {
      await createService(text);
      return;
    }
    if (screen === "service-edit-name") {
      if (!text.trim()) bot(t("frontend.demo_simulator.catalog_error_name"));
      else {
        setBusy(true);
        try {
          const updated = await dataSource.catalog.updateService(selectedServiceId ?? "", { name: text });
          await completeMutation(t("frontend.demo_simulator.catalog_service_renamed", { name: updated.name }));
        } catch (error) {
          bot(errorMessage(error));
        } finally {
          setBusy(false);
        }
      }
      return;
    }
    if (screen === "plan-select" || screen === "plan-delete-select") {
      const service = selectedService();
      if (!service) return goMenu();
      if (text === "8") {
        const servicePlans = plans.filter((plan) => plan.service_id === service.id);
        const last = totalPages(servicePlans) - 1;
        if (page >= last) bot(t("frontend.demo_simulator.no_next_page"));
        else {
          const next = page + 1;
          setPage(next);
          bot(planListText(service.id, next, screen === "plan-delete-select"));
        }
        return;
      }
      const servicePlans = plans.filter((plan) => plan.service_id === service.id);
      const selection = Number.parseInt(text, 10);
      const plan = Number.isInteger(selection) && selection > 0
        ? servicePlans[page * PAGE_SIZE + selection - 1]
        : undefined;
      if (!plan) bot(t("frontend.demo_simulator.invalid_navigation"));
      else if (screen === "plan-delete-select") {
        setSelectedPlanId(plan.id);
        setBusy(true);
        try {
          const nextPreview = await dataSource.catalog.getPlanDeletePreview(service.id, plan.id);
          setPreview(nextPreview);
          setConfirmation("plan-delete");
          setScreen("plan-delete-confirm");
          bot(t("frontend.demo_simulator.catalog_delete_confirm", {
            type: t("frontend.demo_simulator.plan"),
            name: nextPreview.target_name,
            plans: nextPreview.affected_plan_count,
            active: nextPreview.active_subscription_count,
            historical: nextPreview.historical_subscription_count,
          }));
        } catch (error) {
          bot(errorMessage(error));
        } finally {
          setBusy(false);
        }
      } else {
        setSelectedPlanId(plan.id);
        setScreen("plan-detail");
        setPage(0);
        bot(planDetailText(plan));
      }
      return;
    }
    if (screen === "plan-detail") {
      const plan = selectedPlan();
      if (!plan) return goMenu();
      if (text === "1") {
        setScreen("plan-edit-name");
        bot(t("frontend.demo_simulator.catalog_edit_plan_prompt"));
      } else if (text === "2") {
        setBusy(true);
        try {
          const nextPreview = await dataSource.catalog.getPlanDeletePreview(plan.service_id, plan.id);
          setPreview(nextPreview);
          setConfirmation("plan-delete");
          setScreen("plan-delete-confirm");
          bot(t("frontend.demo_simulator.catalog_delete_confirm", {
            type: t("frontend.demo_simulator.plan"),
            name: nextPreview.target_name,
            plans: nextPreview.affected_plan_count,
            active: nextPreview.active_subscription_count,
            historical: nextPreview.historical_subscription_count,
          }));
        } catch (error) {
          bot(errorMessage(error));
        } finally {
          setBusy(false);
        }
      } else bot(t("frontend.demo_simulator.invalid_navigation"));
      return;
    }
    if (screen === "plan-create-name") {
      const service = selectedService();
      if (!service) return goMenu();
      if (!text.trim()) bot(t("frontend.demo_simulator.catalog_error_name"));
      else {
        setBusy(true);
        try {
          const created = await dataSource.catalog.createPlan(service.id, { name: text });
          await completeMutation(t("frontend.demo_simulator.catalog_plan_created", { name: created.name }));
        } catch (error) {
          bot(errorMessage(error));
        } finally {
          setBusy(false);
        }
      }
      return;
    }
    if (screen === "plan-edit-name") {
      const plan = selectedPlan();
      if (!plan) return goMenu();
      if (!text.trim()) bot(t("frontend.demo_simulator.catalog_error_name"));
      else {
        setBusy(true);
        try {
          const updated = await dataSource.catalog.updatePlan(plan.service_id, plan.id, { name: text });
          await completeMutation(t("frontend.demo_simulator.catalog_plan_renamed", { name: updated.name }));
        } catch (error) {
          bot(errorMessage(error));
        } finally {
          setBusy(false);
        }
      }
      return;
    }
    if (screen === "service-delete-confirm" || screen === "plan-delete-confirm") {
      if (!/^confirm(ar)?$/i.test(text) || !confirmation) {
        bot(t("frontend.demo_simulator.catalog_confirm_reprompt"));
        return;
      }
      setBusy(true);
      try {
        if (confirmation === "service-delete") {
          const name = preview?.target_name ?? "";
          await dataSource.catalog.deleteService(selectedServiceId ?? "");
          await completeMutation(t("frontend.demo_simulator.catalog_service_deleted", { name }));
        } else {
          const serviceId = selectedServiceId ?? "";
          const name = preview?.target_name ?? "";
          await dataSource.catalog.deletePlan(serviceId, selectedPlanId ?? "");
          await completeMutation(t("frontend.demo_simulator.catalog_plan_deleted", { name }));
        }
      } catch (error) {
        bot(errorMessage(error));
      } finally {
        setBusy(false);
      }
    }
  }

  async function createService(text: string): Promise<void> {
    if (!text.trim()) {
      bot(t("frontend.demo_simulator.catalog_error_name"));
      return;
    }
    setBusy(true);
    try {
      const created = await dataSource.catalog.createService({ name: text });
      await completeMutation(t("frontend.demo_simulator.catalog_service_created", { name: created.name }));
    } catch (error) {
      bot(errorMessage(error));
    } finally {
      setBusy(false);
    }
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const text = input.trim();
    if (!text || busy || loading) return;
    append("user", text);
    setInput("");
    if (text === "0") {
      onCancel();
      return;
    }
    if (text === "9") {
      goBack();
      return;
    }
    if (section === "clients") await handleClientMessage(text);
    else await handleCatalogMessage(text);
  }

  if (loading) return <div className="flex min-h-[22rem] items-center justify-center text-sm text-muted-foreground" role="status"><Loader2 className={`mr-2 size-4 ${reducedMotion ? "" : "animate-spin"}`} aria-hidden="true" />{t("frontend.demo_simulator.client_loading")}</div>;
  if (loadError) {
    return (
      <Alert variant="destructive">
        <AlertTitle>{t("frontend.demo_simulator.operation_error")}</AlertTitle>
        <AlertDescription className="flex flex-col gap-3">
          <span>{t("frontend.demo_simulator.workspace_error")}</span>
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
        <CardTitle>{section === "clients" ? t("frontend.demo_simulator.clients_title") : t("frontend.demo_simulator.catalog_title")}</CardTitle>
        <CardDescription>{t("frontend.demo_simulator.local_operation_description")}</CardDescription>
      </CardHeader>
      <CardContent className="p-0">
        <TenantAdminMessages messages={messages} />
        <form className="flex gap-2 border-t bg-muted/30 p-3" onSubmit={handleSubmit}>
          <label className="sr-only" htmlFor="tenant-admin-console-input">{t("frontend.demo_simulator.message_input_label")}</label>
          <Input id="tenant-admin-console-input" value={input} onChange={(event) => setInput(event.target.value)} placeholder={t("frontend.demo_simulator.operation_placeholder")} autoComplete="off" autoFocus disabled={busy} />
          <Button type="submit" size="icon" aria-label={t("frontend.demo_simulator.send")} disabled={!input.trim() || busy}><Send className="size-4" aria-hidden="true" /></Button>
        </form>
      </CardContent>
    </Card>
  );
}
