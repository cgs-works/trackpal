import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { CurrencyPicker } from "../currency-picker";

vi.mock("@/i18n", () => ({
  t: (key: string) => key,
  getLocale: () => "en",
}));

const CURRENCIES = [
  { code: "VES", symbol: "Bs.", minor_units: 2 },
  { code: "USD", symbol: "$", minor_units: 2 },
  { code: "EUR", symbol: "€", minor_units: 2 },
];

describe("CurrencyPicker", () => {
  it("renders the official currency first above a separator when a country is selected", async () => {
    render(
      <CurrencyPicker
        value={null}
        currencies={CURRENCIES}
        officialCurrency="VES"
        onChange={() => {}}
      />
    );
    await userEvent.click(screen.getByRole("button"));
    const items = screen.getAllByRole("option").map((el) => el.textContent);
    expect(items[0]).toContain("Bs.");
    // VES appears exactly once (grouped, not duplicated in the rest)
    expect(items.filter((t) => t?.includes("Bs.")).length).toBe(1);
  });

  it("renders a plain list without grouping when no country is selected", async () => {
    render(
      <CurrencyPicker
        value={null}
        currencies={CURRENCIES}
        officialCurrency={null}
        onChange={() => {}}
      />
    );
    await userEvent.click(screen.getByRole("button"));
    const items = screen.getAllByRole("option").map((el) => el.textContent);
    expect(items).toHaveLength(3);
  });

  it("calls onChange with the selected code", async () => {
    const onChange = vi.fn();
    render(
      <CurrencyPicker
        value={null}
        currencies={CURRENCIES}
        officialCurrency="VES"
        onChange={onChange}
      />
    );
    await userEvent.click(screen.getByRole("button"));
    await userEvent.click(screen.getAllByRole("option")[0]);
    expect(onChange).toHaveBeenCalledWith("VES");
  });
});
