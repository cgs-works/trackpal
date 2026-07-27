export interface SimulatorService {
  id: string;
  name: string;
}

export interface SimulatorCopy {
  welcome: string;
  servicePrompt: (services: string) => string;
  emptyServices: string;
  invalidService: string;
  emailPrompt: (service: string) => string;
  invalidEmail: string;
  searching: string;
  codeFound: (service: string, code: string) => string;
  invalidStart: string;
  busy: string;
  cancelled?: string;
  back?: string;
  invalidNavigation?: string;
}

export interface SimulatorMessage {
  id: number;
  role: "bot" | "user";
  text: string;
}

export type SimulatorStep = "idle" | "service" | "email" | "processing" | "complete" | "empty";

export interface SimulatorState {
  step: SimulatorStep;
  services: SimulatorService[];
  selectedService: SimulatorService | null;
  email: string | null;
  code: string | null;
  messages: SimulatorMessage[];
}

export type SimulatorEvent =
  | { type: "message"; text: string }
  | { type: "processing-complete" }
  | { type: "back" }
  | { type: "reset" };

const DEFAULT_COPY: SimulatorCopy = {
  welcome: "Send code to request an access code.",
  servicePrompt: (services) => `Which service do you need?\n${services}`,
  emptyServices: "No enabled service is available. Enable a service in Settings first.",
  invalidService: "Choose one of the listed service numbers.",
  emailPrompt: (service) => `Enter the subscription email for ${service}.`,
  invalidEmail: "Enter a valid email address, for example name@example.com.",
  searching: "Searching the connected demo mailbox…",
  codeFound: (service, code) => `Code found for ${service}: ${code}`,
  invalidStart: "Send code, codigo, or código to start the request.",
  busy: "The demo is still searching. Please wait.",
  cancelled: "Conversation cancelled.",
  back: "Back",
  invalidNavigation: "Choose one of the listed options.",
};

function nextMessageId(messages: SimulatorMessage[]): number {
  return messages.length === 0 ? 1 : messages[messages.length - 1].id + 1;
}

function appendMessage(
  state: SimulatorState,
  role: SimulatorMessage["role"],
  text: string,
): SimulatorState {
  return {
    ...state,
    messages: [...state.messages, { id: nextMessageId(state.messages), role, text }],
  };
}

function normalizeCommand(value: string): string {
  const normalized = value.trim().toLocaleLowerCase().normalize("NFD").replace(/[\u0300-\u036f]/g, "");
  return normalized === "codigo" ? "code" : normalized;
}

function formatServices(services: SimulatorService[]): string {
  return services.map((service, index) => `${index + 1}. ${service.name}`).join("\n");
}

export function isValidSimulatorEmail(value: string): boolean {
  return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(value.trim());
}

export function generateFictitiousCode(serviceId: string, email: string): string {
  let hash = 7;
  for (const character of `${serviceId}:${email.toLocaleLowerCase()}`) {
    hash = (hash * 31 + character.charCodeAt(0)) >>> 0;
  }
  return String(hash % 1_000_000).padStart(6, "0");
}

export function createSimulatorState(
  services: SimulatorService[],
  copy: SimulatorCopy = DEFAULT_COPY,
): SimulatorState {
  return {
    step: "idle",
    services,
    selectedService: null,
    email: null,
    code: null,
    messages: [{ id: 1, role: "bot", text: copy.welcome }],
  };
}

export function transitionSimulator(
  state: SimulatorState,
  event: SimulatorEvent,
  copy: SimulatorCopy = DEFAULT_COPY,
): SimulatorState {
  if (event.type === "reset") {
    return createSimulatorState(state.services, copy);
  }

  if (event.type === "back") {
    if (state.step === "email") {
      return {
        ...appendMessage(state, "bot", copy.servicePrompt(formatServices(state.services))),
        step: "service",
        selectedService: null,
        email: null,
        code: null,
      };
    }
    if (state.step === "service" || state.step === "complete" || state.step === "empty") {
      return {
        ...appendMessage(state, "bot", copy.back ?? copy.invalidStart),
        step: "idle",
        selectedService: null,
        email: null,
        code: null,
      };
    }
    return state;
  }

  if (event.type === "processing-complete") {
    if (state.step !== "processing" || !state.selectedService || !state.email) return state;
    const code = generateFictitiousCode(state.selectedService.id, state.email);
    return appendMessage(
      { ...state, step: "complete", code },
      "bot",
      copy.codeFound(state.selectedService.name, code),
    );
  }

  const text = event.text.trim();
  const withUserMessage = appendMessage(state, "user", text);

  if (state.step === "processing") {
    return appendMessage(withUserMessage, "bot", copy.busy);
  }

  if (text === "0") {
    return {
      ...appendMessage(withUserMessage, "bot", copy.cancelled ?? copy.invalidStart),
      step: "idle",
      selectedService: null,
      email: null,
      code: null,
    };
  }

  if (state.step === "service" && text === "8") {
    return appendMessage(withUserMessage, "bot", copy.invalidNavigation ?? copy.invalidService);
  }

  if (state.step === "idle" || state.step === "complete" || state.step === "empty") {
    if (normalizeCommand(text) !== "code") {
      return appendMessage(withUserMessage, "bot", copy.invalidStart);
    }
    if (state.services.length === 0) {
      return { ...appendMessage(withUserMessage, "bot", copy.emptyServices), step: "empty" };
    }
    return {
      ...appendMessage(withUserMessage, "bot", copy.servicePrompt(formatServices(state.services))),
      step: "service",
      selectedService: null,
      email: null,
      code: null,
    };
  }

  if (state.step === "service") {
    const index = Number.parseInt(text, 10) - 1;
    const service = Number.isInteger(index) && index >= 0 ? state.services[index] : undefined;
    if (!service) {
      return appendMessage(withUserMessage, "bot", copy.invalidService);
    }
    return {
      ...appendMessage(withUserMessage, "bot", copy.emailPrompt(service.name)),
      step: "email",
      selectedService: service,
      email: null,
      code: null,
    };
  }

  if (state.step === "email") {
    if (!isValidSimulatorEmail(text)) {
      return appendMessage(withUserMessage, "bot", copy.invalidEmail);
    }
    return {
      ...appendMessage(withUserMessage, "bot", copy.searching),
      step: "processing",
      email: text.toLocaleLowerCase(),
      code: null,
    };
  }

  return withUserMessage;
}
