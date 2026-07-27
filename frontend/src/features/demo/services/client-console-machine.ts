export interface ClientConsoleClient {
  id: string;
  fullName: string;
  phone: string | null;
  isActive: boolean;
}

export interface ClientConsoleSubscription {
  id: string;
  clientId: string;
  serviceName: string;
  planName: string;
  startsAt: string;
  expiresAt: string;
  status: string;
}

export interface ClientConsoleCopy {
  selectClients: (page: number, totalPages: number) => string;
  clientItem: (number: number, client: ClientConsoleClient) => string;
  emptyClients: string;
  menu: (client: ClientConsoleClient) => string;
  profile: (client: ClientConsoleClient, tenantName: string, status: string) => string;
  subscriptionsHeader: (client: ClientConsoleClient, page: number, totalPages: number) => string;
  subscriptionItem: (number: number, subscription: ClientConsoleSubscription) => string;
  emptySubscriptions: string;
  inactiveSubscriptions: string;
  expiredSubscriptions: string;
  invalid: string;
  noNextPage: string;
  cancelled: string;
  back: string;
  cancel: string;
  next: string;
  accessCode: string;
}

export interface ClientConsoleMessage {
  id: number;
  role: "bot" | "user";
  text: string;
}

export type ClientConsoleScreen =
  | "select"
  | "menu"
  | "profile"
  | "subscriptions"
  | "access-code"
  | "back"
  | "cancelled";

export interface ClientConsoleState {
  screen: ClientConsoleScreen;
  page: number;
  clients: ClientConsoleClient[];
  subscriptions: ClientConsoleSubscription[];
  selectedClientId: string | null;
  referenceTime: string;
  messages: ClientConsoleMessage[];
}

export type ClientConsoleEvent =
  | { type: "message"; text: string }
  | { type: "reset" };

const CLIENT_PAGE_SIZE = 4;
const SUBSCRIPTION_PAGE_SIZE = 3;

function nextMessageId(messages: ClientConsoleMessage[]): number {
  return messages.length === 0 ? 1 : messages[messages.length - 1].id + 1;
}

function appendMessage(
  state: ClientConsoleState,
  role: ClientConsoleMessage["role"],
  text: string,
): ClientConsoleState {
  return {
    ...state,
    messages: [...state.messages, { id: nextMessageId(state.messages), role, text }],
  };
}

function withBot(state: ClientConsoleState, text: string): ClientConsoleState {
  return appendMessage(state, "bot", text);
}

function totalPages(items: unknown[], pageSize: number): number {
  return Math.max(1, Math.ceil(items.length / pageSize));
}

function selectedClient(state: ClientConsoleState): ClientConsoleClient | null {
  return state.clients.find((client) => client.id === state.selectedClientId) ?? null;
}

function clientSubscriptions(state: ClientConsoleState): ClientConsoleSubscription[] {
  return state.subscriptions.filter((subscription) => subscription.clientId === state.selectedClientId);
}

function activeSubscriptions(state: ClientConsoleState): ClientConsoleSubscription[] {
  const reference = new Date(state.referenceTime).getTime();
  return clientSubscriptions(state).filter((subscription) => {
    const expiresAt = new Date(subscription.expiresAt).getTime();
    return subscription.status === "active" &&
      !Number.isNaN(expiresAt) &&
      expiresAt > reference;
  });
}

function emptySubscriptionMessage(
  state: ClientConsoleState,
  client: ClientConsoleClient,
  copy: ClientConsoleCopy,
): string {
  if (!client.isActive) return copy.inactiveSubscriptions;
  if (clientSubscriptions(state).some((subscription) => subscription.status === "expired" || new Date(subscription.expiresAt).getTime() <= new Date(state.referenceTime).getTime())) {
    return copy.expiredSubscriptions;
  }
  return copy.emptySubscriptions;
}

function clientSelectionMessage(
  state: ClientConsoleState,
  copy: ClientConsoleCopy,
): string {
  const total = totalPages(state.clients, CLIENT_PAGE_SIZE);
  const visible = state.clients.slice(
    state.page * CLIENT_PAGE_SIZE,
    (state.page + 1) * CLIENT_PAGE_SIZE,
  );
  const lines = [copy.selectClients(state.page + 1, total)];
  lines.push(...visible.map((client, index) => copy.clientItem(index + 1, client)));
  lines.push(`0. ${copy.cancel}`);
  lines.push(`9. ${copy.back}`);
  if (state.page < total - 1) lines.push(`8. ${copy.next}`);
  return lines.join("\n");
}

function menuState(
  state: ClientConsoleState,
  client: ClientConsoleClient,
  copy: ClientConsoleCopy,
): ClientConsoleState {
  return withBot(
    { ...state, screen: "menu", page: 0 },
    copy.menu(client),
  );
}

function rootState(
  clients: ClientConsoleClient[],
  subscriptions: ClientConsoleSubscription[],
  referenceTime: string,
  copy: ClientConsoleCopy,
): ClientConsoleState {
  const state: ClientConsoleState = {
    screen: "select",
    page: 0,
    clients,
    subscriptions,
    selectedClientId: null,
    referenceTime,
    messages: [],
  };
  return withBot(
    state,
    clients.length > 0 ? clientSelectionMessage(state, copy) : copy.emptyClients,
  );
}

export function createClientConsoleState(
  clients: ClientConsoleClient[],
  subscriptions: ClientConsoleSubscription[],
  referenceTime: string,
  copy: ClientConsoleCopy,
): ClientConsoleState {
  return rootState(clients, subscriptions, referenceTime, copy);
}

export function transitionClientConsole(
  state: ClientConsoleState,
  event: ClientConsoleEvent,
  copy: ClientConsoleCopy,
): ClientConsoleState {
  if (event.type === "reset") {
    return rootState(state.clients, state.subscriptions, state.referenceTime, copy);
  }

  const text = event.text.trim();
  const withUserMessage = appendMessage(state, "user", text);

  if (state.screen === "select") {
    if (text === "0") return withBot({ ...withUserMessage, screen: "cancelled" }, copy.cancelled);
    if (text === "9") return withBot({ ...withUserMessage, screen: "back" }, copy.back);
    if (text === "8") {
      const lastPage = totalPages(state.clients, CLIENT_PAGE_SIZE) - 1;
      if (state.page >= lastPage) return withBot(withUserMessage, copy.noNextPage);
      const next = { ...withUserMessage, page: state.page + 1 };
      return withBot(next, clientSelectionMessage(next, copy));
    }
    const selection = Number.parseInt(text, 10);
    const client = Number.isInteger(selection) && selection > 0
      ? state.clients[state.page * CLIENT_PAGE_SIZE + selection - 1]
      : undefined;
    return client
      ? menuState({ ...withUserMessage, selectedClientId: client.id }, client, copy)
      : withBot(withUserMessage, copy.invalid);
  }

  if (state.screen === "menu") {
    if (text === "0") return withBot({ ...withUserMessage, screen: "cancelled" }, copy.cancelled);
    if (text === "9") {
      const next = { ...withUserMessage, screen: "select" as const, selectedClientId: null, page: 0 };
      return withBot(next, clientSelectionMessage(next, copy));
    }
    const client = selectedClient(state);
    if (!client) return withBot({ ...withUserMessage, screen: "select" }, copy.emptyClients);
    if (text === "1") {
      const status = client.isActive ? "active" : "inactive";
      return withBot(
        { ...withUserMessage, screen: "profile", page: 0 },
        copy.profile(client, "", status),
      );
    }
    if (text === "2") {
      const subscriptions = activeSubscriptions(state);
      const next = { ...withUserMessage, screen: "subscriptions" as const, page: 0 };
      if (subscriptions.length === 0) return withBot(next, emptySubscriptionMessage(state, client, copy));
      const total = totalPages(subscriptions, SUBSCRIPTION_PAGE_SIZE);
      const visible = subscriptions.slice(0, SUBSCRIPTION_PAGE_SIZE);
      return withBot(
        next,
        [
          copy.subscriptionsHeader(client, 1, total),
          ...visible.map((subscription, index) => copy.subscriptionItem(index + 1, subscription)),
          ...(total > 1 ? [`8. ${copy.next}`] : []),
          `9. ${copy.back}`,
          `0. ${copy.cancel}`,
        ].join("\n"),
      );
    }
    if (text === "3") return withBot({ ...withUserMessage, screen: "access-code", page: 0 }, copy.accessCode);
    return withBot(withUserMessage, copy.invalid);
  }

  if (state.screen === "profile" || state.screen === "access-code") {
    if (text === "0") return withBot({ ...withUserMessage, screen: "cancelled" }, copy.cancelled);
    if (text === "9") {
      const client = selectedClient(state);
      return client
        ? menuState({ ...withUserMessage, page: 0 }, client, copy)
        : withBot({ ...withUserMessage, screen: "select", selectedClientId: null }, copy.emptyClients);
    }
    return withBot(withUserMessage, copy.invalid);
  }

  if (state.screen === "subscriptions") {
    if (text === "0") return withBot({ ...withUserMessage, screen: "cancelled" }, copy.cancelled);
    const client = selectedClient(state);
    if (!client) return withBot({ ...withUserMessage, screen: "select", selectedClientId: null }, copy.emptyClients);
    const subscriptions = activeSubscriptions(state);
    const total = totalPages(subscriptions, SUBSCRIPTION_PAGE_SIZE);
    if (text === "8") {
      if (state.page >= total - 1) return withBot(withUserMessage, copy.noNextPage);
      const next = { ...withUserMessage, page: state.page + 1 };
      const visible = subscriptions.slice(next.page * SUBSCRIPTION_PAGE_SIZE, (next.page + 1) * SUBSCRIPTION_PAGE_SIZE);
      return withBot(next, [
        copy.subscriptionsHeader(client, next.page + 1, total),
        ...visible.map((subscription, index) => copy.subscriptionItem(index + 1, subscription)),
        `9. ${copy.back}`,
        `0. ${copy.cancel}`,
      ].join("\n"));
    }
    if (text === "9") {
      if (state.page > 0) {
        const next = { ...withUserMessage, page: state.page - 1 };
        const visible = subscriptions.slice(next.page * SUBSCRIPTION_PAGE_SIZE, (next.page + 1) * SUBSCRIPTION_PAGE_SIZE);
        return withBot(next, [
          copy.subscriptionsHeader(client, next.page + 1, total),
          ...visible.map((subscription, index) => copy.subscriptionItem(index + 1, subscription)),
          ...(next.page < total - 1 ? [`8. ${copy.next}`] : []),
          `9. ${copy.back}`,
          `0. ${copy.cancel}`,
        ].join("\n"));
      }
      return menuState({ ...withUserMessage, page: 0 }, client, copy);
    }
    return withBot(withUserMessage, copy.invalid);
  }

  return withUserMessage;
}

export function getSelectedClient(state: ClientConsoleState): ClientConsoleClient | null {
  return selectedClient(state);
}

