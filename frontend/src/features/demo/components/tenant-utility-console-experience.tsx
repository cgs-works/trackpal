import { useEffect, useMemo, useState } from "react";
import type { FormEvent } from "react";
import { Loader2, Send } from "lucide-react";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { t } from "@/i18n";
import type { Profile } from "@/features/admin/services/settings-api";
import { useAuthStore } from "@/store/auth";
import {
  createSimulatorState,
  isValidSimulatorEmail,
  transitionSimulator,
  type SimulatorCopy,
  type SimulatorService,
  type SimulatorState,
} from "../services/simulator-machine";
import { usePrefersReducedMotion } from "./use-prefers-reduced-motion";

export type TenantUtilitySection = "profile" | "access-control" | "help" | "access-code";

interface TenantUtilityConsoleExperienceProps {
  section: TenantUtilitySection;
  onBack: () => void;
  onCancel: () => void;
  onChanged: () => void;
}

type Message = { id: number; role: "bot" | "user"; text: string };
type ProfileField = "full_name" | "email" | "phone";
type ProfileScreen = "menu" | "edit-fields" | "edit-value";
type AccessControlScreen = "menu" | "list" | "block";

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

function ConsoleCard({
  title,
  description,
  messages,
  input,
  onInputChange,
  onSubmit,
  disabled = false,
}: {
  title: string;
  description: string;
  messages: Message[];
  input: string;
  onInputChange: (value: string) => void;
  onSubmit: (event: FormEvent<HTMLFormElement>) => void;
  disabled?: boolean;
}) {
  return (
    <Card className="mx-auto w-full max-w-md overflow-hidden">
      <CardHeader className="border-b bg-muted/30">
        <CardTitle>{title}</CardTitle>
        <CardDescription>{description}</CardDescription>
      </CardHeader>
      <CardContent className="p-0">
        <Messages messages={messages} />
        <form className="flex gap-2 border-t bg-muted/30 p-3" onSubmit={onSubmit}>
          <label className="sr-only" htmlFor="tenant-utility-input">
            {t("frontend.demo_simulator.message_input_label")}
          </label>
          <Input
            id="tenant-utility-input"
            value={input}
            onChange={(event) => onInputChange(event.target.value)}
            placeholder={t("frontend.demo_simulator.operation_placeholder")}
            autoComplete="off"
            disabled={disabled}
          />
          <Button
            type="submit"
            size="icon"
            aria-label={t("frontend.demo_simulator.send")}
            disabled={!input.trim() || disabled}
          >
            <Send className="size-4" aria-hidden="true" />
          </Button>
        </form>
      </CardContent>
    </Card>
  );
}

function UtilityError({ message }: { message: string }) {
  return (
    <Alert variant="destructive">
      <AlertTitle>{t("frontend.demo_simulator.operation_error")}</AlertTitle>
      <AlertDescription>{message}</AlertDescription>
    </Alert>
  );
}

function profileValue(value: string | null | undefined): string {
  return value?.trim() || "—";
}

function ProfileConsole({
  onBack,
  onCancel,
  onChanged,
}: Omit<TenantUtilityConsoleExperienceProps, "section">) {
  const { dataSource } = useAuthStore();
  const [screen, setScreen] = useState<ProfileScreen>("menu");
  const [profile, setProfile] = useState<Profile | null>(null);
  const [field, setField] = useState<ProfileField | null>(null);
  const [input, setInput] = useState("");
  const [messages, setMessages] = useState<Message[]>([]);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    dataSource.settings.loadProfile()
      .then((nextProfile) => {
        if (cancelled) return;
        setProfile(nextProfile);
        setMessages([{ id: 1, role: "bot", text: profileMenu() }]);
      })
      .catch(() => {
        if (!cancelled) setError(t("frontend.demo_simulator.profile_error"));
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [dataSource.settings]);

  function append(role: Message["role"], text: string) {
    setMessages((current) => [...current, { id: current.length + 1, role, text }]);
  }

  function profileMenu(): string {
    return `${t("frontend.demo_simulator.profile_menu")}\n\n1. ${t("frontend.demo_simulator.profile_view")}\n2. ${t("frontend.demo_simulator.profile_edit")}\n\n9. ${t("frontend.demo_simulator.back")}\n0. ${t("frontend.demo_simulator.cancel")}`;
  }

  function profileDetail(nextProfile: Profile): string {
    return t("frontend.demo_simulator.profile_detail", {
      username: nextProfile.username,
      name: profileValue(nextProfile.full_name ?? nextProfile.name),
      email: profileValue(nextProfile.email),
      phone: profileValue(nextProfile.phone),
    });
  }

  function editFields(): string {
    return `${t("frontend.demo_simulator.profile_edit_fields")}\n\n1. ${t("frontend.profile.full_name")}\n2. ${t("frontend.profile.email")}\n3. ${t("frontend.profile.phone")}\n\n9. ${t("frontend.demo_simulator.back")}\n0. ${t("frontend.demo_simulator.cancel")}`;
  }

  function fieldPrompt(nextField: ProfileField): string {
    return t(`frontend.demo_simulator.profile_edit_${nextField}`);
  }

  function goBackFromProfile() {
    if (screen === "menu") return onBack();
    if (screen === "edit-fields") {
      setScreen("menu");
      append("bot", profileMenu());
      return;
    }
    setScreen("edit-fields");
    append("bot", editFields());
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const text = input.trim();
    if (!text || busy) return;
    setInput("");
    append("user", text);

    if (text === "0") return onCancel();
    if (text === "9") return goBackFromProfile();
    if (!profile) return;

    if (screen === "menu") {
      if (text === "1") {
        append("bot", profileDetail(profile));
      } else if (text === "2") {
        setScreen("edit-fields");
        append("bot", editFields());
      } else {
        append("bot", t("frontend.demo_simulator.invalid_navigation"));
      }
      return;
    }

    if (screen === "edit-fields") {
      const selectedField: ProfileField | undefined = text === "1"
        ? "full_name"
        : text === "2"
          ? "email"
          : text === "3"
            ? "phone"
            : undefined;
      if (!selectedField) {
        append("bot", t("frontend.demo_simulator.invalid_navigation"));
        return;
      }
      setField(selectedField);
      setScreen("edit-value");
      append("bot", fieldPrompt(selectedField));
      return;
    }

    if (!field || !text) return;
    setBusy(true);
    try {
      const updated = await dataSource.settings.updateProfile({ [field]: text });
      setProfile(updated);
      setScreen("menu");
      setField(null);
      onChanged();
      append("bot", `${t("frontend.demo_simulator.profile_updated")}\n\n${profileMenu()}`);
    } catch {
      append("bot", t("frontend.demo_simulator.profile_error"));
      append("bot", fieldPrompt(field));
    } finally {
      setBusy(false);
    }
  }

  if (loading) return <Loading />;
  if (error) return <UtilityError message={error} />;
  return (
    <ConsoleCard
      title={t("frontend.demo_simulator.profile_title")}
      description={t("frontend.demo_simulator.profile_description")}
      messages={messages}
      input={input}
      onInputChange={setInput}
      onSubmit={(event) => void handleSubmit(event)}
      disabled={busy}
    />
  );
}

function AccessControlConsole({
  onBack,
  onCancel,
  onChanged,
}: Omit<TenantUtilityConsoleExperienceProps, "section">) {
  const { dataSource } = useAuthStore();
  const [screen, setScreen] = useState<AccessControlScreen>("menu");
  const [blocks, setBlocks] = useState<Awaited<ReturnType<typeof dataSource.settings.listAccessBlocks>>>([]);
  const [input, setInput] = useState("");
  const [messages, setMessages] = useState<Message[]>([]);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    dataSource.settings.listAccessBlocks()
      .then((nextBlocks) => {
        if (cancelled) return;
        setBlocks(nextBlocks);
        setMessages([{ id: 1, role: "bot", text: accessMenu() }]);
      })
      .catch(() => {
        if (!cancelled) setError(t("frontend.demo_simulator.access_control_error"));
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [dataSource.settings]);

  function append(role: Message["role"], text: string) {
    setMessages((current) => [...current, { id: current.length + 1, role, text }]);
  }

  function accessMenu(): string {
    return `${t("frontend.demo_simulator.access_control_menu")}\n\n1. ${t("frontend.demo_simulator.access_control_list")}\n2. ${t("frontend.demo_simulator.access_control_block")}\n\n9. ${t("frontend.demo_simulator.back")}\n0. ${t("frontend.demo_simulator.cancel")}`;
  }

  function blockList(nextBlocks = blocks): string {
    if (nextBlocks.length === 0) {
      return `${t("frontend.demo_simulator.access_control_empty")}\n\n9. ${t("frontend.demo_simulator.back")}\n0. ${t("frontend.demo_simulator.cancel")}`;
    }
    return `${t("frontend.demo_simulator.access_control_list")}\n\n${nextBlocks.map((block, index) => `${index + 1}. ${block.phone ?? block.whatsapp_lid ?? "—"}`).join("\n")}\n\n${t("frontend.demo_simulator.access_control_unblock_prompt")}\n9. ${t("frontend.demo_simulator.back")}\n0. ${t("frontend.demo_simulator.cancel")}`;
  }

  function goBackFromAccessControl() {
    if (screen === "menu") return onBack();
    setScreen("menu");
    append("bot", accessMenu());
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const text = input.trim();
    if (!text || busy) return;
    setInput("");
    append("user", text);

    if (text === "0") return onCancel();
    if (text === "9") return goBackFromAccessControl();

    if (screen === "menu") {
      if (text === "1") {
        setScreen("list");
        append("bot", blockList());
      } else if (text === "2") {
        setScreen("block");
        append("bot", t("frontend.demo_simulator.access_control_block_prompt"));
      } else {
        append("bot", t("frontend.demo_simulator.invalid_navigation"));
      }
      return;
    }

    if (screen === "list") {
      const selection = Number.parseInt(text, 10);
      const block = Number.isInteger(selection) && selection > 0 ? blocks[selection - 1] : undefined;
      if (!block) {
        append("bot", t("frontend.demo_simulator.invalid_navigation"));
        return;
      }
      setBusy(true);
      try {
        await dataSource.settings.deleteAccessBlock(block.id);
        const nextBlocks = await dataSource.settings.listAccessBlocks();
        setBlocks(nextBlocks);
        onChanged();
        append("bot", `${t("frontend.demo_simulator.access_control_unblocked")}\n\n${blockList(nextBlocks)}`);
      } catch {
        append("bot", t("frontend.demo_simulator.access_control_error"));
      } finally {
        setBusy(false);
      }
      return;
    }

    setBusy(true);
    try {
      await dataSource.settings.createAccessBlock(text);
      const nextBlocks = await dataSource.settings.listAccessBlocks();
      setBlocks(nextBlocks);
      setScreen("menu");
      onChanged();
      append("bot", `${t("frontend.demo_simulator.access_control_blocked")}\n\n${accessMenu()}`);
    } catch (caughtError) {
      const errorCode = caughtError instanceof Error ? caughtError.message : "";
      append("bot", errorCode === "access_block_duplicate"
        ? t("frontend.demo_simulator.access_control_duplicate")
        : t("frontend.demo_simulator.access_control_error"));
      append("bot", t("frontend.demo_simulator.access_control_block_prompt"));
    } finally {
      setBusy(false);
    }
  }

  if (loading) return <Loading />;
  if (error) return <UtilityError message={error} />;
  return (
    <ConsoleCard
      title={t("frontend.demo_simulator.access_control_title")}
      description={t("frontend.demo_simulator.access_control_description")}
      messages={messages}
      input={input}
      onInputChange={setInput}
      onSubmit={(event) => void handleSubmit(event)}
      disabled={busy}
    />
  );
}

function HelpConsole({ onBack, onCancel }: Omit<TenantUtilityConsoleExperienceProps, "section" | "onChanged">) {
  const messages: Message[] = useMemo(() => [{
    id: 1,
    role: "bot",
    text: `${t("frontend.demo_simulator.help_text")}\n\n9. ${t("frontend.demo_simulator.back")}\n0. ${t("frontend.demo_simulator.cancel")}`,
  }], []);
  const [input, setInput] = useState("");

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const text = input.trim();
    if (!text) return;
    setInput("");
    if (text === "0") return onCancel();
    if (text === "9") return onBack();
  }

  return (
    <ConsoleCard
      title={t("frontend.demo_simulator.help_title")}
      description={t("frontend.demo_simulator.help_description")}
      messages={messages}
      input={input}
      onInputChange={setInput}
      onSubmit={handleSubmit}
    />
  );
}

function createTenantCodeCopy(): SimulatorCopy {
  return {
    welcome: t("frontend.demo_simulator.tenant_access_code_welcome"),
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

function CodeLookupConsole({ onBack, onCancel }: Omit<TenantUtilityConsoleExperienceProps, "section" | "onChanged">) {
  const { dataSource } = useAuthStore();
  const reducedMotion = usePrefersReducedMotion();
  const copy = useMemo(() => createTenantCodeCopy(), []);
  const [services, setServices] = useState<SimulatorService[]>([]);
  const [state, setState] = useState<SimulatorState>(() => createSimulatorState([], copy));
  const [input, setInput] = useState("");
  const [inputError, setInputError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    dataSource.settings.loadCodeServices()
      .then((response) => {
        if (cancelled) return;
        const enabled = response.services
          .filter((service) => service.is_selected)
          .map((service) => ({ id: service.service_key, name: service.label }));
        setServices(enabled);
        setState(createSimulatorState(enabled, copy));
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [copy, dataSource.settings]);

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
    if (text === "0") return onCancel();
    if (text === "9") {
      if (state.step === "email") setState((current) => transitionSimulator(current, { type: "back" }, copy));
      else onBack();
      setInput("");
      setInputError(null);
      return;
    }
    if (state.step === "email" && !isValidSimulatorEmail(text)) {
      setInputError(t("frontend.demo_simulator.invalid_email"));
    } else if (state.step === "service") {
      const index = Number.parseInt(text, 10) - 1;
      setInputError(services[index] ? null : t("frontend.demo_simulator.invalid_service"));
    } else {
      setInputError(null);
    }
    setState((current) => transitionSimulator(current, { type: "message", text }, copy));
    setInput("");
  }

  if (loading) return <Loading />;
  return (
    <Card className="mx-auto w-full max-w-md overflow-hidden">
      <CardHeader className="border-b bg-muted/30">
        <CardTitle>{t("frontend.demo_simulator.access_code_title")}</CardTitle>
        <CardDescription>{t("frontend.demo_simulator.access_code_description")}</CardDescription>
      </CardHeader>
      <CardContent className="p-0">
        <Messages messages={state.messages} />
        <form className="flex flex-col gap-2 border-t bg-muted/30 p-3" onSubmit={handleSubmit}>
          <label className="text-xs font-medium text-muted-foreground" htmlFor="tenant-code-input">
            {state.step === "service" ? t("frontend.demo_simulator.service_input_label") : state.step === "email" ? t("frontend.demo_simulator.email_input_label") : t("frontend.demo_simulator.message_input_label")}
          </label>
          <div className="flex gap-2">
            <Input
              id="tenant-code-input"
              value={input}
              onChange={(event) => { setInput(event.target.value); setInputError(null); }}
              placeholder={t("frontend.demo_simulator.operation_placeholder")}
              aria-invalid={Boolean(inputError)}
              aria-describedby={inputError ? "tenant-code-input-error" : undefined}
              autoComplete="off"
              disabled={state.step === "processing"}
            />
            <Button type="submit" size="icon" aria-label={t("frontend.demo_simulator.send")} disabled={!input.trim() || state.step === "processing"}>
              <Send className="size-4" aria-hidden="true" />
            </Button>
          </div>
          {inputError && <p id="tenant-code-input-error" role="alert" className="text-xs text-destructive">{inputError}</p>}
        </form>
      </CardContent>
    </Card>
  );
}

function Loading() {
  const reducedMotion = usePrefersReducedMotion();
  return (
    <div className="flex min-h-[22rem] items-center justify-center text-sm text-muted-foreground" role="status">
      <Loader2 className={`mr-2 size-4 ${reducedMotion ? "" : "animate-spin"}`} aria-hidden="true" />
      {t("frontend.demo_simulator.loading")}
    </div>
  );
}

export function TenantUtilityConsoleExperience({
  section,
  onBack,
  onCancel,
  onChanged,
}: TenantUtilityConsoleExperienceProps) {
  if (section === "profile") return <ProfileConsole onBack={onBack} onCancel={onCancel} onChanged={onChanged} />;
  if (section === "access-control") return <AccessControlConsole onBack={onBack} onCancel={onCancel} onChanged={onChanged} />;
  if (section === "help") return <HelpConsole onBack={onBack} onCancel={onCancel} />;
  return <CodeLookupConsole onBack={onBack} onCancel={onCancel} />;
}
