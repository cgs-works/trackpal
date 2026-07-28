import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { LegalFooter } from "../legal-footer";

vi.mock("@/i18n/public", () => ({
  t: (key: string) => {
    const translations: Record<string, string> = {
      "legal.footer_label": "Legal information",
      "legal.copyright": "© 2026 Camacho Global Software · TrackPal",
      "legal.privacy_policy": "Privacy Policy",
      "legal.terms_of_service": "Terms of Service",
    };
    return translations[key] ?? key;
  },
}));

describe("LegalFooter", () => {
  it("renders the TrackPal brand and exactly two legal links", () => {
    render(<LegalFooter />);

    expect(screen.getByRole("img", { name: "TrackPal" })).toBeInTheDocument();
    expect(
      screen.getByText("© 2026 Camacho Global Software · TrackPal"),
    ).toBeInTheDocument();

    const links = screen.getAllByRole("link");
    expect(links).toHaveLength(2);
    expect(screen.getByRole("link", { name: "Privacy Policy" })).toHaveAttribute(
      "href",
      "https://trackpal.wilfredocamacho.dev/privacy-policy",
    );
    expect(screen.getByRole("link", { name: "Terms of Service" })).toHaveAttribute(
      "href",
      "https://trackpal.wilfredocamacho.dev/terms-of-service",
    );
  });
});
