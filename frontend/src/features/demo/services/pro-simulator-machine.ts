export interface ProSimulatorMenuItem {
  id: string;
  label: string;
}

export interface ProSimulatorCopy {
  welcome: string;
  requestMode: string;
  operationMode: string;
  rolePrompt: string;
  tenantAdminRole: string;
  clientRole: string;
  tenantAdminMenu: (page: number, totalPages: number) => string;
  clientMenu: (page: number, totalPages: number) => string;
  unavailable: string;
  invalid: string;
  noNextPage: string;
  cancelled: string;
  cancel: string;
  back: string;
  next: string;
}

export interface ProSimulatorMessage {
  id: number;
  role: "bot" | "user";
  text: string;
}

export type ProSimulatorMode = "request" | "operation";
export type ProSimulatorRole = "tenant-admin" | "client";
export type ProSimulatorScreen = "mode" | "role" | "menu";

export interface ProSimulatorState {
  screen: ProSimulatorScreen;
  mode: ProSimulatorMode | null;
  role: ProSimulatorRole | null;
  page: number;
  tenantAdminItems: ProSimulatorMenuItem[];
  clientItems: ProSimulatorMenuItem[];
  messages: ProSimulatorMessage[];
}

export type ProSimulatorEvent =
  | { type: "message"; text: string }
  | { type: "select-mode"; mode: ProSimulatorMode }
  | { type: "reset" };

const PAGE_SIZE = 4;

function nextMessageId(messages: ProSimulatorMessage[]): number {
  return messages.length === 0 ? 1 : messages[messages.length - 1].id + 1;
}

function appendMessage(
  state: ProSimulatorState,
  role: ProSimulatorMessage["role"],
  text: string,
): ProSimulatorState {
  return {
    ...state,
    messages: [...state.messages, { id: nextMessageId(state.messages), role, text }],
  };
}

function menuItems(state: ProSimulatorState): ProSimulatorMenuItem[] {
  return state.role === "client" ? state.clientItems : state.tenantAdminItems;
}

function totalPages(items: ProSimulatorMenuItem[]): number {
  return Math.max(1, Math.ceil(items.length / PAGE_SIZE));
}

function menuMessage(
  state: ProSimulatorState,
  copy: ProSimulatorCopy,
): string {
  const items = menuItems(state);
  const start = state.page * PAGE_SIZE;
  const visible = items.slice(start, start + PAGE_SIZE);
  const title = state.role === "client"
    ? copy.clientMenu(state.page + 1, totalPages(items))
    : copy.tenantAdminMenu(state.page + 1, totalPages(items));

  return [
    title,
    ...visible.map((item, index) => `${index + 1}. ${item.label}`),
    `0. ${copy.cancel}`,
    `9. ${copy.back}`,
    ...(state.page < totalPages(items) - 1 ? [`8. ${copy.next}`] : []),
  ].join("\n");
}

function modeMessage(copy: ProSimulatorCopy): string {
  return [
    copy.welcome,
    `1. ${copy.requestMode}`,
    `2. ${copy.operationMode}`,
    `0. ${copy.cancel}`,
  ].join("\n");
}

function roleMessage(copy: ProSimulatorCopy): string {
  return [
    copy.rolePrompt,
    `1. ${copy.tenantAdminRole}`,
    `2. ${copy.clientRole}`,
    `0. ${copy.cancel}`,
    `9. ${copy.back}`,
  ].join("\n");
}

function withBot(state: ProSimulatorState, text: string): ProSimulatorState {
  return appendMessage(state, "bot", text);
}

function rootState(
  tenantAdminItems: ProSimulatorMenuItem[],
  clientItems: ProSimulatorMenuItem[],
  copy: ProSimulatorCopy,
): ProSimulatorState {
  const state: ProSimulatorState = {
    screen: "mode",
    mode: null,
    role: null,
    page: 0,
    tenantAdminItems,
    clientItems,
    messages: [],
  };
  return withBot(state, modeMessage(copy));
}

function chooseMode(
  state: ProSimulatorState,
  mode: ProSimulatorMode,
  copy: ProSimulatorCopy,
): ProSimulatorState {
  if (mode === "request") {
    return withBot(
      { ...state, screen: "mode", mode, role: null, page: 0 },
      copy.requestMode,
    );
  }
  return withBot(
    { ...state, screen: "role", mode, role: null, page: 0 },
    roleMessage(copy),
  );
}

export function createProSimulatorState(
  tenantAdminItems: ProSimulatorMenuItem[],
  clientItems: ProSimulatorMenuItem[],
  copy: ProSimulatorCopy,
): ProSimulatorState {
  return rootState(tenantAdminItems, clientItems, copy);
}

export function transitionProSimulator(
  state: ProSimulatorState,
  event: ProSimulatorEvent,
  copy: ProSimulatorCopy,
): ProSimulatorState {
  if (event.type === "reset") {
    return rootState(state.tenantAdminItems, state.clientItems, copy);
  }

  if (event.type === "select-mode") {
    return chooseMode(state, event.mode, copy);
  }

  const text = event.text.trim();
  const withUserMessage = appendMessage(state, "user", text);

  if (state.screen === "mode") {
    if (text === "0") {
      return withBot(rootState(state.tenantAdminItems, state.clientItems, copy), copy.cancelled);
    }
    if (text === "1") return chooseMode(withUserMessage, "request", copy);
    if (text === "2") return chooseMode(withUserMessage, "operation", copy);
    return withBot(withUserMessage, copy.invalid);
  }

  if (state.screen === "role") {
    if (text === "0") {
      return withBot(rootState(state.tenantAdminItems, state.clientItems, copy), copy.cancelled);
    }
    if (text === "9") return withBot(rootState(state.tenantAdminItems, state.clientItems, copy), modeMessage(copy));
    if (text === "1" || text === "2") {
      const role: ProSimulatorRole = text === "1" ? "tenant-admin" : "client";
      const next = { ...withUserMessage, screen: "menu" as const, role, page: 0 };
      return withBot(next, menuMessage(next, copy));
    }
    return withBot(withUserMessage, copy.invalid);
  }

  if (text === "0") {
    return withBot(rootState(state.tenantAdminItems, state.clientItems, copy), copy.cancelled);
  }
  if (text === "9") {
    if (state.page > 0) {
      const next = { ...withUserMessage, page: state.page - 1 };
      return withBot(next, menuMessage(next, copy));
    }
    return withBot(
      { ...withUserMessage, screen: "role", role: null, page: 0 },
      roleMessage(copy),
    );
  }
  if (text === "8") {
    const lastPage = totalPages(menuItems(state)) - 1;
    if (state.page >= lastPage) return withBot(withUserMessage, copy.noNextPage);
    const next = { ...withUserMessage, page: state.page + 1 };
    return withBot(next, menuMessage(next, copy));
  }

  const selection = Number.parseInt(text, 10);
  const items = menuItems(state);
  const selected = Number.isInteger(selection) && selection > 0
    ? items[state.page * PAGE_SIZE + selection - 1]
    : undefined;
  return selected ? withBot(withUserMessage, copy.unavailable) : withBot(withUserMessage, copy.invalid);
}
