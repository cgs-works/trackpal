import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { DemoEndedPage } from "../demo-ended-page";

vi.mock("@/i18n/public", () => ({
  getLocale: () => "en",
  t: (key: string) => {
    const translations: Record<string, string> = {
      "demo_ended.title": "Demo Unavailable",
      "demo_ended.description":
        "This demo evaluation is no longer available. Contact us to continue the conversation.",
      "demo_ended.contact.whatsapp": "WhatsApp",
      "demo_ended.contact.telegram": "Telegram",
      "demo_ended.contact.email": "Email",
    };
    return translations[key] ?? key;
  },
}));

describe("DemoEndedPage", () => {
  it("renders title and description", () => {
    render(<DemoEndedPage />);
    expect(screen.getByText("Demo Unavailable")).toBeInTheDocument();
    expect(
      screen.getByText(
        "This demo evaluation is no longer available. Contact us to continue the conversation.",
      ),
    ).toBeInTheDocument();
  });

  it("renders WhatsApp as primary contact", () => {
    render(<DemoEndedPage />);
    const whatsapp = screen.getByText("WhatsApp");
    expect(whatsapp).toBeInTheDocument();
    expect(whatsapp.closest("a")).toHaveAttribute(
      "href",
      "https://wa.me/584243106642",
    );
  });

  it("renders Telegram contact", () => {
    render(<DemoEndedPage />);
    const telegram = screen.getByText("Telegram");
    expect(telegram).toBeInTheDocument();
    expect(telegram.closest("a")).toHaveAttribute(
      "href",
      "https://t.me/trackpal",
    );
  });

  it("renders Email contact", () => {
    render(<DemoEndedPage />);
    const email = screen.getByText("Email");
    expect(email).toBeInTheDocument();
    expect(email.closest("a")).toHaveAttribute("href", "mailto:hola@trackpal.app");
  });

  it("opens external links in new tab", () => {
    render(<DemoEndedPage />);
    const whatsapp = screen.getByText("WhatsApp").closest("a")!;
    const telegram = screen.getByText("Telegram").closest("a")!;
    for (const link of [whatsapp, telegram]) {
      expect(link).toHaveAttribute("target", "_blank");
      expect(link).toHaveAttribute("rel", "noopener noreferrer");
    }
  });
});
