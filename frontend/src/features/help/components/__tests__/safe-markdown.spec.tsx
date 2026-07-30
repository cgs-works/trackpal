import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { SafeMarkdown } from "../safe-markdown";

describe("SafeMarkdown", () => {
  it("renders ordered tutorial steps", () => {
    render(<SafeMarkdown source={"1. Enable 2-Step Verification.\n2. Create the password."} />);
    expect(screen.getByRole("list")).toHaveClass("list-decimal");
    expect(screen.getAllByRole("listitem")).toHaveLength(2);
  });

  it("renders allowed Google links safely", () => {
    render(
      <SafeMarkdown
        source={"[Open Google](https://myaccount.google.com/apppasswords)"}
      />,
    );
    expect(screen.getByRole("link", { name: "Open Google" })).toHaveAttribute(
      "target",
      "_blank",
    );
    expect(screen.getByRole("link", { name: "Open Google" })).toHaveAttribute(
      "rel",
      "noopener noreferrer",
    );
  });

  it("renders the second allowed Google link safely", () => {
    render(
      <SafeMarkdown
        source={"[2SV help](https://support.google.com/accounts/answer/185833)"}
      />,
    );
    expect(screen.getByRole("link", { name: "2SV help" })).toHaveAttribute(
      "target",
      "_blank",
    );
  });

  it("does not create a link for an unknown host", () => {
    render(<SafeMarkdown source={"[Unsafe](https://example.com)"} />);
    expect(screen.queryByRole("link")).not.toBeInTheDocument();
  });

  it("degrades to plain text for allowed host with wrong path", () => {
    render(
      <SafeMarkdown
        source={"[Wrong path](https://support.google.com/anything-else)"}
      />,
    );
    expect(screen.queryByRole("link")).not.toBeInTheDocument();
    expect(screen.getByText("Wrong path")).toBeInTheDocument();
  });

  it("degrades to plain text for allowed host with no path", () => {
    render(
      <SafeMarkdown
        source={"[Bare host](https://myaccount.google.com/)"}
      />,
    );
    expect(screen.queryByRole("link")).not.toBeInTheDocument();
    expect(screen.getByText("Bare host")).toBeInTheDocument();
  });
});
