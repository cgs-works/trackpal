import { describe, expect, it } from "vitest";
import {
  createProSimulatorState,
  transitionProSimulator,
  type ProSimulatorCopy,
  type ProSimulatorMenuItem,
} from "../pro-simulator-machine";

const copy: ProSimulatorCopy = {
  welcome: "Choose a mode",
  requestMode: "Request mode",
  operationMode: "Operation mode",
  rolePrompt: "Choose a console",
  tenantAdminRole: "Tenant Admin",
  clientRole: "Client",
  tenantAdminMenu: (page, total) => `Tenant Admin page ${page}/${total}`,
  clientMenu: (page, total) => `Client page ${page}/${total}`,
  unavailable: "This operation is coming later",
  invalid: "Choose a listed option",
  noNextPage: "There is no next page",
  cancelled: "Conversation cancelled",
  cancel: "Cancel",
  back: "Back",
  next: "Next",
};

const tenantItems: ProSimulatorMenuItem[] = [
  { id: "clients", label: "Clients" },
  { id: "catalog", label: "Catalog" },
  { id: "profile", label: "My profile" },
  { id: "subscriptions", label: "Subscriptions" },
  { id: "access", label: "Access control" },
  { id: "help", label: "Help" },
  { id: "code", label: "Access code" },
];
const clientItems: ProSimulatorMenuItem[] = [
  { id: "profile", label: "View profile" },
  { id: "subscriptions", label: "Active subscriptions" },
  { id: "code", label: "Access code" },
];

function step(state: ReturnType<typeof createProSimulatorState>, text: string) {
  return transitionProSimulator(state, { type: "message", text }, copy);
}

describe("Pro simulator machine", () => {
  it("selects Request and Operation modes from the Pro root", () => {
    const root = createProSimulatorState(tenantItems, clientItems, copy);
    const request = step(root, "1");
    const operation = step(root, "2");

    expect(request.mode).toBe("request");
    expect(request.screen).toBe("mode");
    expect(request.messages.at(-1)?.text).toContain("Request mode");
    expect(operation.screen).toBe("role");
  });

  it("shows both documented console roots and paginates Tenant Admin", () => {
    const role = step(step(createProSimulatorState(tenantItems, clientItems, copy), "2"), "1");
    const next = step(role, "8");
    const back = step(next, "9");
    const client = step(step(createProSimulatorState(tenantItems, clientItems, copy), "2"), "2");

    expect(role.role).toBe("tenant-admin");
    expect(role.page).toBe(0);
    expect(role.messages.at(-1)?.text).toContain("Clients");
    expect(next.page).toBe(1);
    expect(next.messages.at(-1)?.text).toContain("Access code");
    expect(back.page).toBe(0);
    expect(client.role).toBe("client");
    expect(client.messages.at(-1)?.text).toContain("View profile");
  });

  it("keeps invalid navigation and pagination boundaries cancellable", () => {
    const root = createProSimulatorState(tenantItems, clientItems, copy);
    const invalid = step(root, "7");
    const operation = step(root, "2");
    const client = step(step(operation, "2"), "8");
    const cancelled = step(client, "0");

    expect(invalid.screen).toBe("mode");
    expect(invalid.messages.at(-1)?.text).toBe("Choose a listed option");
    expect(client.page).toBe(0);
    expect(client.messages.at(-1)?.text).toBe("There is no next page");
    expect(cancelled.screen).toBe("mode");
    expect(cancelled.mode).toBeNull();
  });

  it("uses 9 to back through the screen stack and leaves operation details deferred", () => {
    const root = createProSimulatorState(tenantItems, clientItems, copy);
    const operation = step(root, "2");
    const tenant = step(operation, "1");
    const deferred = step(tenant, "1");
    const role = step(deferred, "9");
    const mode = step(role, "9");

    expect(deferred.screen).toBe("menu");
    expect(deferred.messages.at(-1)?.text).toBe("This operation is coming later");
    expect(role.screen).toBe("role");
    expect(mode.screen).toBe("mode");
  });
});
