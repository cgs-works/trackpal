import { describe, expect, it } from "vitest";
import {
  createSimulatorState,
  generateFictitiousCode,
  transitionSimulator,
  type SimulatorService,
} from "../simulator-machine";

const services: SimulatorService[] = [
  { id: "netflix", name: "Netflix" },
  { id: "disney", name: "Disney+" },
];

describe("simulator machine", () => {
  it("accepts every localized access-code trigger from the idle state", () => {
    for (const trigger of ["code", "codigo", "código"]) {
      const next = transitionSimulator(createSimulatorState(services), {
        type: "message",
        text: trigger,
      });

      expect(next.step).toBe("service");
      expect(next.messages.at(-1)?.text).toContain("Netflix");
      expect(next.messages.at(-1)?.text).toContain("Disney+");
    }
  });

  it("normalizes whitespace and rejects unrelated idle messages", () => {
    const next = transitionSimulator(createSimulatorState(services), {
      type: "message",
      text: "  hello  ",
    });

    expect(next.step).toBe("idle");
    expect(next.messages.at(-1)?.text).toContain("code");
  });

  it("provides an explicit empty state when no service is enabled", () => {
    const next = transitionSimulator(createSimulatorState([]), {
      type: "message",
      text: "code",
    });

    expect(next.step).toBe("empty");
    expect(next.messages.at(-1)?.text).toContain("service");
  });

  it("re-prompts after invalid service selection and accepts a valid one", () => {
    const started = transitionSimulator(createSimulatorState(services), {
      type: "message",
      text: "code",
    });
    const invalid = transitionSimulator(started, {
      type: "message",
      text: "9",
    });
    const selected = transitionSimulator(invalid, {
      type: "message",
      text: "2",
    });

    expect(invalid.step).toBe("service");
    expect(invalid.messages.at(-1)?.text).toContain("listed");
    expect(selected.step).toBe("email");
    expect(selected.selectedService).toEqual(services[1]);
  });

  it("re-prompts for an email-shaped value and starts local progress for valid input", () => {
    const selected = transitionSimulator(
      transitionSimulator(createSimulatorState(services), {
        type: "message",
        text: "code",
      }),
      { type: "message", text: "1" },
    );
    const invalid = transitionSimulator(selected, {
      type: "message",
      text: "not-an-email",
    });
    const processing = transitionSimulator(invalid, {
      type: "message",
      text: "member@example.test",
    });

    expect(invalid.step).toBe("email");
    expect(invalid.messages.at(-1)?.text).toContain("email");
    expect(processing.step).toBe("processing");
    expect(processing.email).toBe("member@example.test");
  });

  it("emits a deterministic six-digit fictitious code after local progress", () => {
    const processing = {
      ...createSimulatorState(services),
      step: "processing" as const,
      selectedService: services[0],
      email: "member@example.test",
    };
    const completed = transitionSimulator(processing, { type: "processing-complete" });

    expect(completed.step).toBe("complete");
    expect(completed.code).toMatch(/^\d{6}$/);
    expect(completed.code).toBe(generateFictitiousCode(services[0].id, "member@example.test"));
  });

  it("uses the caller's localized copy without changing transitions", () => {
    const spanishCopy = {
      welcome: "Envía codigo",
      servicePrompt: (items: string) => `Servicio\n${items}`,
      emptyServices: "Sin servicios",
      invalidService: "Elige un servicio",
      emailPrompt: (service: string) => `Correo para ${service}`,
      invalidEmail: "Correo inválido",
      searching: "Buscando",
      codeFound: (service: string, code: string) => `Código ${service} ${code}`,
      invalidStart: "Envía codigo",
      busy: "Espera",
    };
    const next = transitionSimulator(
      createSimulatorState(services, spanishCopy),
      { type: "message", text: "codigo" },
      spanishCopy,
    );

    expect(next.messages.at(-1)?.text).toContain("Servicio");
  });

  it("resets only the conversation state", () => {
    const state = transitionSimulator(createSimulatorState(services), {
      type: "message",
      text: "code",
    });

    expect(transitionSimulator(state, { type: "reset" })).toEqual(
      createSimulatorState(services),
    );
  });
});
