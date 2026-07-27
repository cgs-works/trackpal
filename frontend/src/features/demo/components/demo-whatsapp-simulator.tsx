import { useEffect, useMemo, useState } from "react";
import type { FormEvent } from "react";
import { ArrowLeft, Check, Loader2, MessageCircle, RotateCcw, Send } from "lucide-react";
import { Link } from "@tanstack/react-router";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { NotFoundPage } from "@/features/admin/components/not-found-page";
import { t } from "@/i18n";
import { useAuthStore } from "@/store/auth";
import {
  createSimulatorState,
  isValidSimulatorEmail,
  transitionSimulator,
  type SimulatorCopy,
  type SimulatorState,
} from "../services/simulator-machine";
import {
  createProSimulatorState,
  transitionProSimulator,
  type ProSimulatorCopy,
  type ProSimulatorMenuItem,
  type ProSimulatorMode,
  type ProSimulatorState,
} from "../services/pro-simulator-machine";
import { ClientConsoleExperience } from "./client-console-experience";
import { SubscriptionConsoleExperience } from "./subscription-console-experience";
import { TenantAdminConsoleExperience } from "./tenant-admin-console-experience";
import {
  TenantUtilityConsoleExperience,
  type TenantUtilitySection,
} from "./tenant-utility-console-experience";
import { usePrefersReducedMotion } from "./use-prefers-reduced-motion";

function createSimulatorCopy(): SimulatorCopy {
  return {
    welcome: t("frontend.demo_simulator.welcome"),
    servicePrompt: (services) => t("frontend.demo_simulator.service_prompt", { services }),
    emptyServices: t("frontend.demo_simulator.empty_services"),
    invalidService: t("frontend.demo_simulator.invalid_service"),
    emailPrompt: (service) => t("frontend.demo_simulator.email_prompt", { service }),
    invalidEmail: t("frontend.demo_simulator.invalid_email"),
    searching: t("frontend.demo_simulator.searching"),
    codeFound: (service, code) => t("frontend.demo_simulator.code_found", { service, code }),
    invalidStart: t("frontend.demo_simulator.invalid_start"),
    busy: t("frontend.demo_simulator.busy"),
  };
}

function simulatorInputText(step: SimulatorState["step"]): {
  label: string;
  placeholder: string;
} {
  if (step === "service") {
    return {
      label: t("frontend.demo_simulator.service_input_label"),
      placeholder: t("frontend.demo_simulator.service_placeholder"),
    };
  }
  if (step === "email") {
    return {
      label: t("frontend.demo_simulator.email_input_label"),
      placeholder: t("frontend.demo_simulator.email_placeholder"),
    };
  }
  return {
    label: t("frontend.demo_simulator.message_input_label"),
    placeholder: t("frontend.demo_simulator.message_placeholder"),
  };
}

function messageBubbleClass(role: "bot" | "user"): string {
  return role === "user"
    ? "ml-auto max-w-[85%] rounded-2xl rounded-br-sm bg-primary px-3 py-2 text-primary-foreground"
    : "max-w-[85%] rounded-2xl rounded-bl-sm bg-muted px-3 py-2 text-foreground";
}

function SimulatorMessages({ state }: { state: SimulatorState }) {
  return (
    <div
      className="flex min-h-[22rem] flex-col gap-3 overflow-y-auto rounded-t-xl bg-background p-4 sm:min-h-[25rem]"
      role="log"
      aria-label={t("frontend.demo_simulator.conversation")}
      aria-live="polite"
    >
      {state.messages.map((message) => (
        <div key={message.id} className={messageBubbleClass(message.role)}>
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
  );
}

function ProSimulatorMessages({ state }: { state: ProSimulatorState }) {
  return (
    <div
      className="flex min-h-[22rem] flex-col gap-3 overflow-y-auto rounded-t-xl bg-background p-4"
      role="log"
      aria-label={t("frontend.demo_simulator.conversation")}
      aria-live="polite"
    >
      {state.messages.map((message) => (
        <div key={message.id} className={messageBubbleClass(message.role)}>
          <p className="whitespace-pre-wrap text-sm leading-relaxed">{message.text}</p>
        </div>
      ))}
    </div>
  );
}

function createProSimulatorCopy(): ProSimulatorCopy {
  return {
    welcome: t("frontend.demo_simulator.welcome"),
    requestMode: t("frontend.demo_simulator.mode_request"),
    operationMode: t("frontend.demo_simulator.mode_operation"),
    rolePrompt: t("frontend.demo_simulator.role_prompt"),
    tenantAdminRole: t("frontend.demo_simulator.role_tenant_admin"),
    clientRole: t("frontend.demo_simulator.role_client"),
    tenantAdminMenu: (page, total) => t("frontend.demo_simulator.tenant_menu", { page, total }),
    clientMenu: (page, total) => t("frontend.demo_simulator.client_menu", { page, total }),
    unavailable: t("frontend.demo_simulator.operation_unavailable"),
    invalid: t("frontend.demo_simulator.invalid_navigation"),
    noNextPage: t("frontend.demo_simulator.no_next_page"),
    cancelled: t("frontend.demo_simulator.cancelled"),
    cancel: t("frontend.demo_simulator.cancel"),
    back: t("frontend.demo_simulator.back"),
    next: t("frontend.demo_simulator.next"),
  };
}

function createProMenuItems(): { tenantAdmin: ProSimulatorMenuItem[]; client: ProSimulatorMenuItem[] } {
  return {
    tenantAdmin: [
      { id: "clients", label: t("frontend.demo_simulator.menu_clients") },
      { id: "catalog", label: t("frontend.demo_simulator.menu_catalog") },
      { id: "profile", label: t("frontend.demo_simulator.menu_profile") },
      { id: "subscriptions", label: t("frontend.demo_simulator.menu_subscriptions") },
      { id: "access-control", label: t("frontend.demo_simulator.menu_access_control") },
      { id: "help", label: t("frontend.demo_simulator.menu_help") },
      { id: "access-code", label: t("frontend.demo_simulator.menu_access_code") },
    ],
    client: [
      { id: "profile", label: t("frontend.demo_simulator.menu_view_profile") },
      { id: "subscriptions", label: t("frontend.demo_simulator.menu_active_subscriptions") },
      { id: "access-code", label: t("frontend.demo_simulator.menu_access_code") },
    ],
  };
}

function ProRequestExperience() {
  const { dataSource } = useAuthStore();
  const reducedMotion = usePrefersReducedMotion();
  const copy = useMemo(() => createSimulatorCopy(), []);
  const [state, setState] = useState<SimulatorState>(() => createSimulatorState([], copy));
  const [input, setInput] = useState("");
  const [inputError, setInputError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState(false);
  const [loadAttempt, setLoadAttempt] = useState(0);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setLoadError(false);
    dataSource.settings.loadCodeServices().then((response) => {
      if (cancelled) return;
      const services = response.services
        .filter((service) => service.is_selected)
        .map((service) => ({ id: service.service_key, name: service.label }));
      setState(createSimulatorState(services, copy));
      setLoading(false);
    }).catch(() => {
      if (!cancelled) {
        setLoadError(true);
        setLoading(false);
      }
    });
    return () => {
      cancelled = true;
    };
  }, [copy, dataSource, loadAttempt]);

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
    if (!text || state.step === "processing") return;
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

  if (loading) {
    return <div className="flex min-h-[22rem] items-center justify-center text-sm text-muted-foreground" role="status">{t("frontend.demo_simulator.loading")}</div>;
  }
  if (loadError) {
    return (
      <Alert variant="destructive">
        <AlertTitle>{t("frontend.demo_simulator.operation_error")}</AlertTitle>
        <AlertDescription className="flex flex-col gap-3">
          <span>{t("frontend.demo_simulator.load_error")}</span>
          <Button type="button" variant="outline" onClick={() => setLoadAttempt((attempt) => attempt + 1)}>
            {t("frontend.demo_simulator.retry")}
          </Button>
        </AlertDescription>
      </Alert>
    );
  }

  const { label: inputLabel, placeholder: inputPlaceholder } = simulatorInputText(
    state.step,
  );

  return (
    <Card className="mx-auto w-full max-w-md overflow-hidden">
      <CardHeader className="border-b bg-muted/30">
        <CardTitle>{t("frontend.demo_simulator.request_title")}</CardTitle>
        <CardDescription>{t("frontend.demo_simulator.request_description")}</CardDescription>
      </CardHeader>
      <CardContent className="p-0">
        <SimulatorMessages state={state} />
        <form className="flex flex-col gap-2 border-t bg-muted/30 p-3" onSubmit={handleSubmit}>
          <label className="text-xs font-medium text-muted-foreground" htmlFor="pro-simulator-input">{inputLabel}</label>
          <div className="flex gap-2">
            <Input
              id="pro-simulator-input"
              value={input}
              onChange={(event) => { setInput(event.target.value); setInputError(null); }}
              placeholder={inputPlaceholder}
              aria-invalid={Boolean(inputError)}
              aria-describedby={inputError ? "pro-simulator-input-error" : undefined}
              disabled={state.step === "processing"}
              autoComplete="off"
              autoFocus
            />
            <Button type="submit" size="icon" aria-label={t("frontend.demo_simulator.send")} disabled={!input.trim() || state.step === "processing"}>
              <Send className="size-4" aria-hidden="true" />
            </Button>
          </div>
          {inputError && <p id="pro-simulator-input-error" role="alert" className="text-xs text-destructive">{inputError}</p>}
        </form>
      </CardContent>
    </Card>
  );
}

function ProOperationExperience() {
  const { dataSource } = useAuthStore();
  const copy = useMemo(() => createProSimulatorCopy(), []);
  const menus = useMemo(() => createProMenuItems(), []);
  const [state, setState] = useState<ProSimulatorState>(() =>
    transitionProSimulator(
      createProSimulatorState(menus.tenantAdmin, menus.client, copy, 7),
      { type: "select-mode", mode: "operation" },
      copy,
    ),
  );
  const [input, setInput] = useState("");
  const [clientConsole, setClientConsole] = useState(false);
  const [tenantAdminConsole, setTenantAdminConsole] = useState<
    "clients" | "catalog" | "subscriptions" | TenantUtilitySection | null
  >(null);
  const [summaryVersion, setSummaryVersion] = useState(0);
  const [summary, setSummary] = useState({ clients: 0, services: 0, subscriptions: 0, codeServices: 0 });
  const [summaryError, setSummaryError] = useState(false);

  useEffect(() => {
    let cancelled = false;
    Promise.all([
      dataSource.crud.clients.list(),
      dataSource.catalog.listServices(),
      dataSource.subscriptions.list(),
      dataSource.settings.loadCodeServices(),
    ]).then(([clients, services, subscriptions, codeServices]) => {
      if (cancelled) return;
      setSummary({
        clients: clients.length,
        services: services.length,
        subscriptions: subscriptions.length,
        codeServices: codeServices.services.filter((service) => service.is_selected).length,
      });
      setSummaryError(false);
    }).catch(() => {
      if (!cancelled) setSummaryError(true);
    });
    return () => {
      cancelled = true;
    };
  }, [dataSource, summaryVersion]);

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const text = input.trim();
    if (!text) return;
    if (state.screen === "role" && text === "2") {
      setState((current) => transitionProSimulator(current, { type: "message", text }, copy));
      setClientConsole(true);
      setInput("");
      return;
    }
    if (state.screen === "menu" && state.role === "tenant-admin") {
      const selection = Number.parseInt(text, 10);
      const selectedItem = Number.isInteger(selection) && selection > 0
        ? state.tenantAdminItems[state.page * state.tenantAdminPageSize + selection - 1]
        : undefined;
      const consoleByMenuItem: Partial<Record<string, "clients" | "catalog" | "subscriptions" | TenantUtilitySection>> = {
        clients: "clients",
        catalog: "catalog",
        subscriptions: "subscriptions",
        profile: "profile",
        "access-control": "access-control",
        help: "help",
        "access-code": "access-code",
      };
      const nextConsole = selectedItem ? consoleByMenuItem[selectedItem.id] : undefined;
      if (nextConsole) {
        setState((current) => transitionProSimulator(current, { type: "message", text }, copy));
        setTenantAdminConsole(nextConsole);
        setInput("");
        return;
      }
    }
    setState((current) => transitionProSimulator(current, { type: "message", text }, copy));
    setInput("");
  }

  if (clientConsole) {
    return (
      <ClientConsoleExperience
        onBack={() => {
          setClientConsole(false);
          setState((current) => transitionProSimulator(current, { type: "message", text: "9" }, copy));
        }}
        onCancel={() => {
          setClientConsole(false);
          setState((current) => transitionProSimulator(current, { type: "message", text: "0" }, copy));
        }}
      />
    );
  }

  if (tenantAdminConsole === "subscriptions") {
    return (
      <SubscriptionConsoleExperience
        onBack={() => setTenantAdminConsole(null)}
        onCancel={() => {
          setTenantAdminConsole(null);
          setState((current) => transitionProSimulator(current, { type: "message", text: "0" }, copy));
        }}
        onChanged={() => setSummaryVersion((version) => version + 1)}
      />
    );
  }

  if (tenantAdminConsole === "profile" || tenantAdminConsole === "access-control" || tenantAdminConsole === "help" || tenantAdminConsole === "access-code") {
    return (
      <TenantUtilityConsoleExperience
        section={tenantAdminConsole}
        onBack={() => setTenantAdminConsole(null)}
        onCancel={() => {
          setTenantAdminConsole(null);
          setState((current) => transitionProSimulator(current, { type: "message", text: "0" }, copy));
        }}
        onChanged={() => setSummaryVersion((version) => version + 1)}
      />
    );
  }

  if (tenantAdminConsole === "clients" || tenantAdminConsole === "catalog") {
    return (
      <TenantAdminConsoleExperience
        section={tenantAdminConsole}
        onBack={() => setTenantAdminConsole(null)}
        onCancel={() => {
          setTenantAdminConsole(null);
          setState((current) => transitionProSimulator(current, { type: "message", text: "0" }, copy));
        }}
        onChanged={() => setSummaryVersion((version) => version + 1)}
      />
    );
  }

  return (
    <div className="grid gap-6 lg:grid-cols-[minmax(0,28rem)_minmax(0,1fr)] lg:items-start">
      <Card className="mx-auto w-full max-w-md overflow-hidden">
        <CardHeader className="border-b bg-muted/30">
          <CardTitle>{t("frontend.demo_simulator.operation_title")}</CardTitle>
          <CardDescription>{t("frontend.demo_simulator.operation_description")}</CardDescription>
        </CardHeader>
        <CardContent className="p-0">
          <ProSimulatorMessages state={state} />
          <form className="flex gap-2 border-t bg-muted/30 p-3" onSubmit={handleSubmit}>
            <label className="sr-only" htmlFor="pro-operation-input">{t("frontend.demo_simulator.message_input_label")}</label>
            <Input id="pro-operation-input" value={input} onChange={(event) => setInput(event.target.value)} placeholder={t("frontend.demo_simulator.operation_placeholder")} autoComplete="off" />
            <Button type="submit" size="icon" aria-label={t("frontend.demo_simulator.send")} disabled={!input.trim()}><Send className="size-4" aria-hidden="true" /></Button>
          </form>
        </CardContent>
      </Card>
      <Card>
        <CardHeader>
          <CardTitle>{t("frontend.demo_simulator.workspace_title")}</CardTitle>
          <CardDescription>{t("frontend.demo_simulator.workspace_description")}</CardDescription>
        </CardHeader>
        <CardContent className="grid gap-3 sm:grid-cols-2">
          {summaryError && (
            <div role="alert" className="flex flex-wrap items-center gap-3 sm:col-span-2 text-sm text-destructive">
              <span>{t("frontend.demo_simulator.workspace_error")}</span>
              <Button type="button" variant="outline" size="sm" onClick={() => setSummaryVersion((version) => version + 1)}>
                {t("frontend.demo_simulator.retry")}
              </Button>
            </div>
          )}
          {[
            [t("frontend.demo_simulator.workspace_clients"), summary.clients],
            [t("frontend.demo_simulator.workspace_services"), summary.services],
            [t("frontend.demo_simulator.workspace_subscriptions"), summary.subscriptions],
            [t("frontend.demo_simulator.workspace_code_services"), summary.codeServices],
          ].map(([label, value]) => (
            <div key={label} className="rounded-lg border bg-muted/30 p-4">
              <p className="text-2xl font-semibold tabular-nums">{value}</p>
              <p className="text-sm text-muted-foreground">{label}</p>
            </div>
          ))}
        </CardContent>
      </Card>
    </div>
  );
}

function ProSimulatorView() {
  const [mode, setMode] = useState<ProSimulatorMode>("request");
  const [resetVersion, setResetVersion] = useState(0);

  function handleModeChange(value: string) {
    setMode(value as ProSimulatorMode);
    setResetVersion((version) => version + 1);
  }

  return (
    <div className="flex-1 p-4 sm:p-6 lg:p-8" data-testid="demo-whatsapp-simulator">
      <div className="mx-auto flex max-w-5xl flex-col gap-6">
        <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
          <div>
            <h1 className="font-heading text-2xl font-semibold tracking-tight">{t("frontend.demo_simulator.title")}</h1>
            <p className="mt-1 text-muted-foreground">{t("frontend.demo_simulator.description")}</p>
          </div>
          <Button type="button" variant="outline" onClick={() => setResetVersion((version) => version + 1)}>
            <RotateCcw data-icon="inline-start" />
            {t("frontend.demo_simulator.reset")}
          </Button>
        </div>
        <Alert>
          <MessageCircle aria-hidden="true" />
          <AlertTitle>{t("frontend.demo_simulator.contained_title")}</AlertTitle>
          <AlertDescription>{t("frontend.demo_simulator.contained_description")}</AlertDescription>
        </Alert>
        <Tabs value={mode} onValueChange={handleModeChange} className="w-full">
          <TabsList className="grid w-full grid-cols-2 sm:w-fit">
            <TabsTrigger value="request">{t("frontend.demo_simulator.mode_request")}</TabsTrigger>
            <TabsTrigger value="operation">{t("frontend.demo_simulator.mode_operation")}</TabsTrigger>
          </TabsList>
          <TabsContent value="request" className="pt-4"><ProRequestExperience key={`request-${resetVersion}`} /></TabsContent>
          <TabsContent value="operation" className="pt-4"><ProOperationExperience key={`operation-${resetVersion}`} /></TabsContent>
        </Tabs>
      </div>
    </div>
  );
}

export function DemoWhatsappSimulator() {
  const { dataSource, demo, tenantPlan, role, isAuthenticated, isMasterSupportContext } = useAuthStore();
  const reducedMotion = usePrefersReducedMotion();
  const copy = useMemo(() => createSimulatorCopy(), []);
  const [state, setState] = useState<SimulatorState>(() => createSimulatorState([], copy));
  const [input, setInput] = useState("");
  const [inputError, setInputError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState(false);
  const [loadAttempt, setLoadAttempt] = useState(0);

  const isDemoSimulator =
    isAuthenticated &&
    role === "tenant" &&
    !isMasterSupportContext &&
    dataSource.mode === "demo" &&
    (demo?.plan === "starter" || demo?.plan === "pro") &&
    tenantPlan === demo.plan;
  const isStarterDemo = isDemoSimulator && demo?.plan === "starter";

  useEffect(() => {
    if (!isStarterDemo) return;
    let cancelled = false;
    setLoading(true);
    setLoadError(false);

    dataSource.settings.loadCodeServices()
      .then((response) => {
        if (cancelled) return;
        const services = response.services
          .filter((service) => service.is_selected)
          .map((service) => ({ id: service.service_key, name: service.label }));
        setState(createSimulatorState(services, copy));
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
  }, [copy, dataSource, isStarterDemo, loadAttempt]);

  useEffect(() => {
    if (state.step !== "processing") return;
    const timer = window.setTimeout(() => {
      setState((current) => transitionSimulator(current, { type: "processing-complete" }, copy));
    }, reducedMotion ? 0 : 900);
    return () => window.clearTimeout(timer);
  }, [copy, reducedMotion, state.step]);

  if (!isDemoSimulator) return <NotFoundPage />;
  if (demo?.plan === "pro") return <ProSimulatorView />;

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const text = input.trim();
    if (!text || state.step === "processing") return;

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

  function handleReset() {
    setState((current) => transitionSimulator(current, { type: "reset" }, copy));
    setInput("");
    setInputError(null);
  }

  const { label: inputLabel, placeholder: inputPlaceholder } = simulatorInputText(
    state.step,
  );
  const inputInvalid = Boolean(inputError);

  function renderConversation() {
    if (loading) {
      return (
        <div className="flex min-h-[22rem] items-center justify-center p-6 text-sm text-muted-foreground" role="status">
          {t("frontend.demo_simulator.loading")}
        </div>
      );
    }
    if (loadError) {
      return (
        <div className="flex min-h-[22rem] flex-col items-center justify-center gap-3 p-6 text-center">
          <p className="text-sm text-destructive">{t("frontend.demo_simulator.load_error")}</p>
          <Button type="button" variant="outline" onClick={() => setLoadAttempt((attempt) => attempt + 1)}>
            {t("frontend.demo_simulator.retry")}
          </Button>
        </div>
      );
    }
    return (
      <>
        <SimulatorMessages state={state} />
        <form className="flex flex-col gap-2 border-t bg-muted/30 p-3" onSubmit={handleSubmit}>
          <label className="text-xs font-medium text-muted-foreground" htmlFor="demo-simulator-input">
            {inputLabel}
          </label>
          <div className="flex gap-2">
            <Input
              id="demo-simulator-input"
              value={input}
              onChange={(event) => {
                setInput(event.target.value);
                setInputError(null);
              }}
              placeholder={inputPlaceholder}
              aria-invalid={inputInvalid}
              aria-describedby={inputInvalid ? "demo-simulator-input-error" : undefined}
              disabled={state.step === "processing"}
              autoComplete="off"
              autoFocus
            />
            <Button type="submit" size="icon" aria-label={t("frontend.demo_simulator.send")} disabled={!input.trim() || state.step === "processing"}>
              <Send className="size-4" aria-hidden="true" />
            </Button>
          </div>
          {inputError && (
            <p id="demo-simulator-input-error" role="alert" className="text-xs text-destructive">
              {inputError}
            </p>
          )}
        </form>
      </>
    );
  }

  return (
    <div className="flex-1 p-4 sm:p-6 lg:p-8" data-testid="demo-whatsapp-simulator">
      <div className="mx-auto flex max-w-5xl flex-col gap-6">
        <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
          <div className="flex items-start gap-3">
            <Link
              to="/admin/settings"
              search={{ category: "whatsapp-link" }}
              className="mt-1 inline-flex size-9 shrink-0 items-center justify-center rounded-md border text-muted-foreground transition-colors hover:bg-accent hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
              aria-label={t("frontend.demo_simulator.back_to_settings")}
            >
              <ArrowLeft className="size-4" aria-hidden="true" />
            </Link>
            <div>
              <div className="flex flex-wrap items-center gap-2">
                <h1 className="font-heading text-2xl font-semibold tracking-tight">
                  {t("frontend.demo_simulator.title")}
                </h1>
                <Badge variant="secondary">{t("frontend.master.demos.starter")}</Badge>
              </div>
              <p className="mt-1 text-muted-foreground">{t("frontend.demo_simulator.description")}</p>
            </div>
          </div>
          <Button type="button" variant="outline" onClick={handleReset} disabled={loading}>
            <RotateCcw data-icon="inline-start" />
            {t("frontend.demo_simulator.reset")}
          </Button>
        </div>

        <Alert>
          <MessageCircle aria-hidden="true" />
          <AlertTitle>{t("frontend.demo_simulator.contained_title")}</AlertTitle>
          <AlertDescription>{t("frontend.demo_simulator.contained_description")}</AlertDescription>
        </Alert>

        <div className="grid gap-6 lg:grid-cols-[minmax(0,28rem)_minmax(0,1fr)] lg:items-start">
          <Card className="mx-auto w-full max-w-md overflow-hidden">
            <CardHeader className="border-b bg-muted/30">
              <div className="flex items-center gap-3">
                <div className="flex size-10 items-center justify-center rounded-full bg-primary/10 text-primary">
                  <MessageCircle className="size-5" aria-hidden="true" />
                </div>
                <div className="min-w-0">
                  <CardTitle className="truncate">TrackPal</CardTitle>
                  <CardDescription className="flex items-center gap-1">
                    <span className="size-2 rounded-full bg-emerald-500" aria-hidden="true" />
                    {t("frontend.demo_simulator.connected")}
                  </CardDescription>
                </div>
                <Check className="ml-auto size-5 text-emerald-600" aria-label={t("frontend.demo_simulator.simulated_status")} />
              </div>
            </CardHeader>
            <CardContent className="p-0">{renderConversation()}</CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>{t("frontend.demo_simulator.request_title")}</CardTitle>
              <CardDescription>{t("frontend.demo_simulator.request_description")}</CardDescription>
            </CardHeader>
            <CardContent className="flex flex-col gap-4 text-sm">
              <div className="rounded-lg border bg-muted/30 p-4">
                <p className="font-medium">{t("frontend.demo_simulator.workspace_title")}</p>
                <p className="mt-1 text-muted-foreground">{t("frontend.demo_simulator.workspace_description")}</p>
              </div>
              <div className="rounded-lg border p-4">
                <p className="font-medium">{t("frontend.demo_simulator.services_title")}</p>
                {state.services.length > 0 ? (
                  <ul className="mt-2 list-inside list-disc text-muted-foreground">
                    {state.services.map((service) => <li key={service.id}>{service.name}</li>)}
                  </ul>
                ) : (
                  <p className="mt-2 text-muted-foreground">{t("frontend.demo_simulator.empty_services")}</p>
                )}
              </div>
              <p className="text-xs text-muted-foreground">{t("frontend.demo_simulator.no_operation_notice")}</p>
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  );
}
