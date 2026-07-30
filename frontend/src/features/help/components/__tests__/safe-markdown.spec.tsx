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

  it("does not create a link for an unknown host", () => {
    render(<SafeMarkdown source={"[Unsafe](https://example.com)"} />);
    expect(screen.queryByRole("link")).not.toBeInTheDocument();
  });
});
