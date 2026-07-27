import { useEffect, useMemo, useState } from "react";
import type { FormEvent } from "react";
import { ArrowLeft, Check, Loader2, MessageCircle, RotateCcw, Send } from "lucide-react";
import { Link } from "@tanstack/react-router";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
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

function usePrefersReducedMotion(): boolean {
  const [reducedMotion, setReducedMotion] = useState(() =>
    typeof window !== "undefined" && window.matchMedia("(prefers-reduced-motion: reduce)").matches,
  );

  useEffect(() => {
    const mediaQuery = window.matchMedia("(prefers-reduced-motion: reduce)");
    const update = () => setReducedMotion(mediaQuery.matches);
    update();
    mediaQuery.addEventListener("change", update);
    return () => mediaQuery.removeEventListener("change", update);
  }, []);

  return reducedMotion;
}

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

export function DemoWhatsappSimulator() {
  const { dataSource, demo, tenantPlan, role, isAuthenticated, isMasterSupportContext } = useAuthStore();
  const reducedMotion = usePrefersReducedMotion();
  const copy = useMemo(() => createSimulatorCopy(), []);
  const [state, setState] = useState<SimulatorState>(() => createSimulatorState([], copy));
  const [input, setInput] = useState("");
  const [inputError, setInputError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState(false);

  const isStarterDemo =
    isAuthenticated &&
    role === "tenant" &&
    !isMasterSupportContext &&
    dataSource.mode === "demo" &&
    demo?.plan === "starter" &&
    tenantPlan === "starter";

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
  }, [copy, dataSource, isStarterDemo]);

  useEffect(() => {
    if (state.step !== "processing") return;
    const timer = window.setTimeout(() => {
      setState((current) => transitionSimulator(current, { type: "processing-complete" }, copy));
    }, reducedMotion ? 0 : 900);
    return () => window.clearTimeout(timer);
  }, [copy, reducedMotion, state.step]);

  if (!isStarterDemo) return <NotFoundPage />;

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

  const inputLabel =
    state.step === "service"
      ? t("frontend.demo_simulator.service_input_label")
      : state.step === "email"
        ? t("frontend.demo_simulator.email_input_label")
        : t("frontend.demo_simulator.message_input_label");
  const inputPlaceholder =
    state.step === "service"
      ? t("frontend.demo_simulator.service_placeholder")
      : state.step === "email"
        ? t("frontend.demo_simulator.email_placeholder")
        : t("frontend.demo_simulator.message_placeholder");
  const inputInvalid = Boolean(inputError);

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
            <CardContent className="p-0">
              {loading ? (
                <div className="flex min-h-[22rem] items-center justify-center p-6 text-sm text-muted-foreground" role="status">
                  {t("frontend.demo_simulator.loading")}
                </div>
              ) : loadError ? (
                <div className="flex min-h-[22rem] flex-col items-center justify-center gap-3 p-6 text-center">
                  <p className="text-sm text-destructive">{t("frontend.demo_simulator.load_error")}</p>
                  <Button type="button" variant="outline" onClick={() => window.location.reload()}>
                    {t("frontend.demo_simulator.retry")}
                  </Button>
                </div>
              ) : (
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
              )}
            </CardContent>
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
