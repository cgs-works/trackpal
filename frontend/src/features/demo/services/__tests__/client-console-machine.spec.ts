import { describe, expect, it } from "vitest";
import {
  createClientConsoleState,
  transitionClientConsole,
  type ClientConsoleClient,
  type ClientConsoleCopy,
  type ClientConsoleSubscription,
} from "../client-console-machine";

const copy: ClientConsoleCopy = {
  selectClients: (page, total) => `Select client · page ${page}/${total}`,
  clientItem: (number, client) => `${number}. ${client.fullName}`,
  emptyClients: "No clients",
  menu: (client) => `Client menu · ${client.fullName}`,
  profile: (client, tenantName, status) => `Profile · ${client.fullName} · ${tenantName} · ${status}`,
  subscriptionsHeader: (client, page, total) => `Subscriptions · ${client.fullName} · page ${page}/${total}`,
  subscriptionItem: (number, subscription) => `${number}. ${subscription.serviceName} · ${subscription.planName}`,
  emptySubscriptions: "No active subscriptions",
  inactiveSubscriptions: "Inactive client",
  expiredSubscriptions: "Expired subscriptions",
  invalid: "Invalid",
  noNextPage: "No next page",
  cancelled: "Cancelled",
  back: "Back",
  cancel: "Cancel",
  next: "Next",
  accessCode: "Access code",
};

const clients: ClientConsoleClient[] = [
  { id: "client-1", fullName: "Avery Stone", phone: "14155552671", isActive: true },
  { id: "client-2", fullName: "Mina Duarte", phone: "14155552672", isActive: true },
  { id: "client-3", fullName: "Leo Chen", phone: "14155552673", isActive: true },
  { id: "client-4", fullName: "Priya Nair", phone: "14155552674", isActive: false },
  { id: "client-5", fullName: "Jon Bell", phone: "14155552675", isActive: false },
];

const subscriptions: ClientConsoleSubscription[] = [
  { id: "sub-1", clientId: "client-1", serviceName: "Secure Messaging", planName: "Basic", startsAt: "2026-07-01T00:00:00.000Z", expiresAt: "2026-08-01T00:00:00.000Z", status: "active" },
  { id: "sub-2", clientId: "client-1", serviceName: "Account Access", planName: "Premium", startsAt: "2026-07-01T00:00:00.000Z", expiresAt: "2026-08-02T00:00:00.000Z", status: "active" },
  { id: "sub-3", clientId: "client-1", serviceName: "Verification Hub", planName: "Professional", startsAt: "2026-07-01T00:00:00.000Z", expiresAt: "2026-08-03T00:00:00.000Z", status: "active" },
  { id: "sub-4", clientId: "client-1", serviceName: "Secure Messaging", planName: "Plus", startsAt: "2026-07-01T00:00:00.000Z", expiresAt: "2026-08-04T00:00:00.000Z", status: "active" },
  { id: "expired", clientId: "client-2", serviceName: "Secure Messaging", planName: "Basic", startsAt: "2026-06-01T00:00:00.000Z", expiresAt: "2026-06-30T00:00:00.000Z", status: "expired" },
];

function step(state: ReturnType<typeof createClientConsoleState>, text: string) {
  return transitionClientConsole(state, { type: "message", text }, copy);
}

describe("Client console machine", () => {
  it("paginates clients and opens a read-only profile", () => {
    const root = createClientConsoleState(clients, subscriptions, "2026-07-25T00:00:00.000Z", copy);
    const next = step(root, "8");
    const selected = step(next, "1");
    const profile = step(selected, "1");

    expect(next.page).toBe(1);
    expect(next.messages.at(-1)?.text).toContain("Jon Bell");
    expect(selected.selectedClientId).toBe("client-5");
    expect(profile.screen).toBe("profile");
    expect(profile.messages.at(-1)?.text).toContain("Jon Bell");
  });

  it("shows only non-expired subscriptions and paginates them", () => {
    const root = createClientConsoleState(clients, subscriptions, "2026-07-25T00:00:00.000Z", copy);
    const client = step(root, "1");
    const list = step(client, "2");
    const page = step(list, "8");
    const back = step(page, "9");

    expect(list.messages.at(-1)?.text).toContain("Secure Messaging");
    expect(list.messages.at(-1)?.text).not.toContain("expired");
    expect(page.page).toBe(1);
    expect(page.messages.at(-1)?.text).toContain("Plus");
    expect(back.page).toBe(0);
  });

  it("handles inactive and expired subscription contexts without mutation", () => {
    const root = createClientConsoleState(clients, subscriptions, "2026-07-25T00:00:00.000Z", copy);
    const inactive = step(step(root, "8"), "1");
    const inactiveSubscriptions = step(inactive, "2");
    const expiredClient = step(root, "2");
    const expiredSubscriptions = step(expiredClient, "2");

    expect(inactiveSubscriptions.screen).toBe("subscriptions");
    expect(inactiveSubscriptions.messages.at(-1)?.text).toBe("Inactive client");
    expect(expiredSubscriptions.messages.at(-1)?.text).toBe("Expired subscriptions");
    expect(expiredSubscriptions.subscriptions).toHaveLength(5);
  });

  it("keeps cancel and back navigation available at every read-only screen", () => {
    const root = createClientConsoleState(clients, subscriptions, "2026-07-25T00:00:00.000Z", copy);
    const client = step(root, "1");
    const profile = step(client, "1");
    const menu = step(profile, "9");
    const accessCode = step(menu, "3");
    const back = step(accessCode, "9");
    const cancelled = step(back, "0");

    expect(accessCode.screen).toBe("access-code");
    expect(back.screen).toBe("menu");
    expect(cancelled.screen).toBe("cancelled");
  });
});
