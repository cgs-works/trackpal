import { useEffect, useMemo, useState } from "react";
import type { FormEvent } from "react";
import { Loader2, Send } from "lucide-react";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { t } from "@/i18n";
import { useAuthStore } from "@/store/auth";
import {
  createSimulatorState,
  isValidSimulatorEmail,
  transitionSimulator,
  type SimulatorCopy,
  type SimulatorService,
  type SimulatorState,
} from "../services/simulator-machine";
import {
  createClientConsoleState,
  getSelectedClient,
  transitionClientConsole,
  type ClientConsoleClient,
  type ClientConsoleCopy,
  type ClientConsoleState,
  type ClientConsoleSubscription,
} from "../services/client-console-machine";
import { usePrefersReducedMotion } from "./use-prefers-reduced-motion";

interface ClientConsoleExperienceProps {
  onBack: () => void;
  onCancel: () => void;
}

function formatDate(value: string): string {
  const date = new Date(value);
  return Number.isNaN(date.getTime())
    ? value
    : new Intl.DateTimeFormat(undefined, { dateStyle: "medium" }).format(date);
}

function createClientConsoleCopy(tenantName: string): ClientConsoleCopy {
  return {
    selectClients: (page, totalPages) => t("frontend.demo_simulator.client_select", { page, total: totalPages }),
    clientItem: (number, client) => t("frontend.demo_simulator.client_item", {
      number,
      name: client.fullName,
      status: client.isActive
        ? t("frontend.demo_simulator.client_active")
        : t("frontend.demo_simulator.client_inactive"),
    }),
    emptyClients: t("frontend.demo_simulator.client_empty"),
    menu: (client) => t("frontend.demo_simulator.client_menu_detail", { name: client.fullName }),
    profile: (client, _unusedTenantName, status) => t("frontend.demo_simulator.client_profile", {
      name: client.fullName,
      provider: tenantName,
      phone: client.phone ?? t("frontend.demo_simulator.client_phone_missing"),
      status: status === "active"
        ? t("frontend.demo_simulator.client_active")
        : t("frontend.demo_simulator.client_inactive"),
    }),
    subscriptionsHeader: (client, page, totalPages) => t("frontend.demo_simulator.client_subscriptions", {
      name: client.fullName,
      page,
      total: totalPages,
    }),
    subscriptionItem: (number, subscription) => t("frontend.demo_simulator.client_subscription_item", {
      number,
      service: subscription.serviceName,
      plan: subscription.planName,
      starts: formatDate(subscription.startsAt),
      expires: formatDate(subscription.expiresAt),
    }),
    emptySubscriptions: t("frontend.demo_simulator.client_subscriptions_empty"),
    inactiveSubscriptions: t("frontend.demo_simulator.client_subscriptions_inactive"),
    expiredSubscriptions: t("frontend.demo_simulator.client_subscriptions_expired"),
    invalid: t("frontend.demo_simulator.invalid_navigation"),
    noNextPage: t("frontend.demo_simulator.no_next_page"),
    cancelled: t("frontend.demo_simulator.cancelled"),
    back: t("frontend.demo_simulator.back"),
    cancel: t("frontend.demo_simulator.cancel"),
    next: t("frontend.demo_simulator.next"),
    accessCode: t("frontend.demo_simulator.client_access_code_selected"),
  };
}

function createClientCodeCopy(): SimulatorCopy {
  return {
    welcome: t("frontend.demo_simulator.client_access_code_welcome"),
    servicePrompt: (services) => t("frontend.demo_simulator.service_prompt", { services }),
    emptyServices: t("frontend.demo_simulator.empty_services"),
    invalidService: t("frontend.demo_simulator.invalid_service"),
    emailPrompt: (service) => t("frontend.demo_simulator.email_prompt", { service }),
    invalidEmail: t("frontend.demo_simulator.invalid_email"),
    searching: t("frontend.demo_simulator.searching"),
    codeFound: (service, code) => t("frontend.demo_simulator.code_found", { service, code }),
    invalidStart: t("frontend.demo_simulator.invalid_start"),
    busy: t("frontend.demo_simulator.busy"),
    cancelled: t("frontend.demo_simulator.cancelled"),
    back: t("frontend.demo_simulator.back"),
    invalidNavigation: t("frontend.demo_simulator.invalid_navigation"),
  };
}

function ClientConsoleMessages({ state }: { state: ClientConsoleState }) {
  return (
    <div
      className="flex min-h-[22rem] flex-col gap-3 overflow-y-auto rounded-t-xl bg-background p-4"
      role="log"
      aria-label={t("frontend.demo_simulator.conversation")}
      aria-live="polite"
    >
      {state.messages.map((message) => (
        <div
          key={message.id}
          className={message.role === "user"
            ? "ml-auto max-w-[85%] rounded-2xl rounded-br-sm bg-primary px-3 py-2 text-primary-foreground"
            : "max-w-[85%] rounded-2xl rounded-bl-sm bg-muted px-3 py-2 text-foreground"}
        >
          <p className="whitespace-pre-wrap text-sm leading-relaxed">{message.text}</p>
        </div>
      ))}
    </div>
  );
}

function ClientCodeExperience({
  services,
  onBack,
  onCancel,
}: {
  services: SimulatorService[];
  onBack: () => void;
  onCancel: () => void;
}) {
  const reducedMotion = usePrefersReducedMotion();
  const copy = useMemo(() => createClientCodeCopy(), []);
  const [state, setState] = useState<SimulatorState>(() => createSimulatorState(services, copy));
  const [input, setInput] = useState("");
  const [inputError, setInputError] = useState<string | null>(null);

  useEffect(() => {
    if (state.step !== "processing") return;
    const timer = window.setTimeout(() => {
      setState((current) => transitionSimulator(current, { type: "processing-complete" }, copy));
    }, reducedMotion ? 0 : 900);
    return () => window.clearTimeout(timer);
  }, [copy, reducedMotion, state.step]);

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const text = input.trim();
    if (!text) return;
    if (text === "0") {
      onCancel();
      return;
    }
    if (text === "9") {
      if (state.step === "email") {
        setState((current) => transitionSimulator(current, { type: "back" }, copy));
      } else {
        onBack();
      }
      setInput("");
      setInputError(null);
      return;
    }

    if (state.step === "email" && !isValidSimulatorEmail(text)) {
      setInputError(t("frontend.demo_simulator.invalid_email"));
    } else if (state.step === "service") {
      const index = Number.parseInt(text, 10) - 1;
      setInputError(state.services[index] ? null : t("frontend.demo_simulator.invalid_service"));
    } else {
      setInputError(null);
    }
    setState((current) => transitionSimulator(current, { type: "message", text }, copy));
    setInput("");
  }

  const inputLabel = state.step === "service"
    ? t("frontend.demo_simulator.service_input_label")
    : state.step === "email"
      ? t("frontend.demo_simulator.email_input_label")
      : t("frontend.demo_simulator.message_input_label");
  const inputPlaceholder = state.step === "service"
    ? t("frontend.demo_simulator.service_placeholder")
    : state.step === "email"
      ? t("frontend.demo_simulator.email_placeholder")
      : t("frontend.demo_simulator.message_placeholder");

  return (
    <Card className="mx-auto w-full max-w-md overflow-hidden">
      <CardHeader className="border-b bg-muted/30">
        <CardTitle>{t("frontend.demo_simulator.client_access_code_title")}</CardTitle>
        <CardDescription>{t("frontend.demo_simulator.client_access_code_description")}</CardDescription>
      </CardHeader>
      <CardContent className="p-0">
        <div
          className="flex min-h-[22rem] flex-col gap-3 overflow-y-auto rounded-t-xl bg-background p-4"
          role="log"
          aria-label={t("frontend.demo_simulator.conversation")}
          aria-live="polite"
        >
          {state.messages.map((message) => (
            <div
              key={message.id}
              className={message.role === "user"
                ? "ml-auto max-w-[85%] rounded-2xl rounded-br-sm bg-primary px-3 py-2 text-primary-foreground"
                : "max-w-[85%] rounded-2xl rounded-bl-sm bg-muted px-3 py-2 text-foreground"}
            >
              <p className="whitespace-pre-wrap text-sm leading-relaxed">{message.text}</p>
            </div>
          ))}
          {state.step === "processing" && (
            <div className="flex max-w-[85%] items-center gap-2 rounded-2xl rounded-bl-sm bg-muted px-3 py-2 text-sm text-muted-foreground" role="status">
              <Loader2 className="size-4 animate-spin motion-reduce:animate-none" aria-hidden="true" />
              {t("frontend.demo_simulator.searching")}
            </div>
          )}
        </div>
        <form className="flex flex-col gap-2 border-t bg-muted/30 p-3" onSubmit={handleSubmit}>
          <label className="text-xs font-medium text-muted-foreground" htmlFor="client-code-input">{inputLabel}</label>
          <div className="flex gap-2">
            <Input
              id="client-code-input"
              value={input}
              onChange={(event) => { setInput(event.target.value); setInputError(null); }}
              placeholder={inputPlaceholder}
              aria-invalid={Boolean(inputError)}
              aria-describedby={inputError ? "client-code-input-error" : undefined}
              autoComplete="off"
            />
            <Button type="submit" size="icon" aria-label={t("frontend.demo_simulator.send")} disabled={!input.trim()}>
              <Send className="size-4" aria-hidden="true" />
            </Button>
          </div>
          {inputError && <p id="client-code-input-error" role="alert" className="text-xs text-destructive">{inputError}</p>}
        </form>
      </CardContent>
    </Card>
  );
}

export function ClientConsoleExperience({ onBack, onCancel }: ClientConsoleExperienceProps) {
  const { dataSource, demo } = useAuthStore();
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState(false);
  const [loadAttempt, setLoadAttempt] = useState(0);
  const [tenantName, setTenantName] = useState(demo?.name ?? "");
  const [services, setServices] = useState<SimulatorService[]>([]);
  const [input, setInput] = useState("");
  const [state, setState] = useState<ClientConsoleState>(() =>
    createClientConsoleState([], [], demo?.serverTime ?? new Date().toISOString(), createClientConsoleCopy(demo?.name ?? "")),
  );
  const copy = useMemo(() => createClientConsoleCopy(tenantName), [tenantName]);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setLoadError(false);

    Promise.all([
      dataSource.crud.clients.list(),
      dataSource.subscriptions.list(),
      dataSource.catalog.listServices(),
      dataSource.settings.loadProfile(),
      dataSource.settings.loadCodeServices(),
    ])
      .then(async ([clients, subscriptions, serviceRecords, profile, codeServices]) => {
        const planRecords = await Promise.all(serviceRecords.map((service) => dataSource.catalog.listPlans(service.id)));
        if (cancelled) return;
        const serviceNames = new Map(serviceRecords.map((service) => [service.id, service.name]));
        const planNames = new Map(planRecords.flat().map((plan) => [plan.id, plan.name]));
        const clientRecords: ClientConsoleClient[] = clients.map((client) => ({
          id: client.id,
          fullName: client.full_name,
          phone: client.phone,
          isActive: client.is_active,
        }));
        const subscriptionRecords: ClientConsoleSubscription[] = subscriptions.map((subscription) => ({
          id: subscription.id,
          clientId: subscription.client_id,
          serviceName: serviceNames.get(subscription.service_id) ?? t("frontend.demo_simulator.unknown_service"),
          planName: planNames.get(subscription.plan_id) ?? t("frontend.demo_simulator.unknown_plan"),
          startsAt: subscription.starts_at,
          expiresAt: subscription.expires_at,
          status: subscription.status,
        }));
        const profileName = profile.tenant_name ?? demo?.name ?? "";
        const selectedServices = codeServices.services
          .filter((service) => service.is_selected)
          .map((service) => ({ id: service.service_key, name: service.label }));
        setTenantName(profileName);
        setServices(selectedServices);
        setState(createClientConsoleState(
          clientRecords,
          subscriptionRecords,
          demo?.serverTime ?? new Date().toISOString(),
          createClientConsoleCopy(profileName),
        ));
        setLoading(false);
      })
      .catch(() => {
        if (!cancelled) {
          setLoadError(true);
          setLoading(false);
        }
      });

    return () => {
      cancelled = true;
    };
  }, [dataSource, demo?.name, demo?.serverTime, loadAttempt]);

  useEffect(() => {
    if (state.screen === "back") onBack();
    if (state.screen === "cancelled") onCancel();
  }, [onBack, onCancel, state.screen]);

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const text = input.trim();
    if (!text) return;
    setState((current) => transitionClientConsole(current, { type: "message", text }, copy));
    setInput("");
  }

  if (loading) {
    return <div className="flex min-h-[22rem] items-center justify-center text-sm text-muted-foreground" role="status">{t("frontend.demo_simulator.client_loading")}</div>;
  }
  if (loadError) {
    return (
      <Alert variant="destructive">
        <AlertTitle>{t("frontend.demo_simulator.client_load_error")}</AlertTitle>
        <AlertDescription className="flex flex-col gap-3">
          <span>{t("frontend.demo_simulator.workspace_error")}</span>
          <Button type="button" variant="outline" onClick={() => setLoadAttempt((attempt) => attempt + 1)}>
            {t("frontend.demo_simulator.retry")}
          </Button>
        </AlertDescription>
      </Alert>
    );
  }

  if (state.screen === "access-code") {
    return (
      <ClientCodeExperience
        services={services}
        onBack={() => setState((current) => transitionClientConsole(current, { type: "message", text: "9" }, copy))}
        onCancel={onCancel}
      />
    );
  }

  const selectedClient = getSelectedClient(state);

  return (
    <Card className="mx-auto w-full max-w-md overflow-hidden">
      <CardHeader className="border-b bg-muted/30">
        <CardTitle>{t("frontend.demo_simulator.client_console_title")}</CardTitle>
        <CardDescription>
          {selectedClient
            ? t("frontend.demo_simulator.client_console_selected", { name: selectedClient.fullName })
            : t("frontend.demo_simulator.client_console_description")}
        </CardDescription>
      </CardHeader>
      <CardContent className="p-0">
        <ClientConsoleMessages state={state} />
        <form className="flex gap-2 border-t bg-muted/30 p-3" onSubmit={handleSubmit}>
          <label className="sr-only" htmlFor="client-console-input">{t("frontend.demo_simulator.message_input_label")}</label>
          <Input
            id="client-console-input"
            name="client-console-input"
            value={input}
            onChange={(event) => setInput(event.target.value)}
            placeholder={t("frontend.demo_simulator.operation_placeholder")}
            autoComplete="off"
            autoFocus
          />
          <Button type="submit" size="icon" aria-label={t("frontend.demo_simulator.send")}>
            <Send className="size-4" aria-hidden="true" />
          </Button>
        </form>
      </CardContent>
    </Card>
  );
}
