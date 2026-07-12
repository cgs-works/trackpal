import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { AccessControlSection } from "../access-control-section";
import {
  createAccessBlock,
  deleteAccessBlock,
  listAccessBlocks,
  type AccessControlBlock,
} from "../../services/access-control-api";

vi.mock("sonner", () => ({
  toast: { success: vi.fn(), error: vi.fn() },
}));

vi.mock("@/i18n", () => ({
  t: (key: string, params?: Record<string, unknown>) => {
    if (!params) return key;
    return `${key} ${Object.values(params).join(" ")}`;
  },
}));

vi.mock("../../services/access-control-api", () => ({
  listAccessBlocks: vi.fn(),
  createAccessBlock: vi.fn(),
  deleteAccessBlock: vi.fn(),
}));

function block(
  id: number,
  overrides: Partial<AccessControlBlock> = {},
): AccessControlBlock {
  return {
    id: `block-${id}`,
    tenant_id: "tenant-1",
    phone: `12015550${String(id).padStart(3, "0")}`,
    whatsapp_lid: null,
    created_at: "2026-06-27T00:00:00Z",
    updated_at: "2026-06-27T00:00:00Z",
    ...overrides,
  };
}

describe("AccessControlSection", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("renders only 10 blocked identities on the first page", async () => {
    vi.mocked(listAccessBlocks).mockResolvedValue(Array.from({ length: 12 }, (_, index) => block(index + 1)));

    render(<AccessControlSection />);

    expect(await screen.findByText("12015550001")).toBeInTheDocument();
    expect(screen.getByText("12015550010")).toBeInTheDocument();
    expect(screen.queryByText("12015550011")).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: "frontend.access_control.pagination_page 2" })).toBeInTheDocument();
  });

  it("uses page numbers and previous-next controls", async () => {
    const user = userEvent.setup();
    vi.mocked(listAccessBlocks).mockResolvedValue(Array.from({ length: 12 }, (_, index) => block(index + 1)));

    render(<AccessControlSection />);

    await screen.findByText("12015550001");
    await user.click(screen.getByRole("button", { name: "frontend.access_control.pagination_next" }));
    expect(screen.queryByText("12015550001")).not.toBeInTheDocument();
    expect(screen.getByText("12015550011")).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "frontend.access_control.pagination_previous" }));
    expect(screen.getByText("12015550001")).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "frontend.access_control.pagination_page 2" }));
    expect(screen.getByText("12015550012")).toBeInTheDocument();
  });

  it("refreshes and removes an unblocked item from the visible list", async () => {
    const user = userEvent.setup();
    vi.mocked(listAccessBlocks)
      .mockResolvedValueOnce([block(1), block(2)])
      .mockResolvedValueOnce([block(2)]);
    vi.mocked(deleteAccessBlock).mockResolvedValue(undefined);

    render(<AccessControlSection />);

    expect(await screen.findByText("12015550001")).toBeInTheDocument();
    await user.click(screen.getAllByRole("button", { name: "frontend.access_control.unblock" })[0]);

    await waitFor(() => expect(deleteAccessBlock).toHaveBeenCalledWith("block-1"));
    await waitFor(() => expect(screen.queryByText("12015550001")).not.toBeInTheDocument());
    expect(screen.getByText("12015550002")).toBeInTheDocument();
  });

  it("refreshes after blocking without breaking pagination", async () => {
    const user = userEvent.setup();
    vi.mocked(listAccessBlocks)
      .mockResolvedValueOnce([])
      .mockResolvedValueOnce([block(1)]);
    vi.mocked(createAccessBlock).mockResolvedValue(block(1));

    render(<AccessControlSection />);

    await screen.findByText("frontend.access_control.empty");
    expect(
      screen.queryByRole("textbox", {
        name: "frontend.access_control.search_label",
      }),
    ).not.toBeInTheDocument();

    await user.type(
      screen.getByPlaceholderText("frontend.access_control.phone_placeholder"),
      "+12015550001",
    );
    await user.click(
      screen.getByRole("button", { name: "frontend.access_control.block" }),
    );

    await waitFor(() =>
      expect(createAccessBlock).toHaveBeenCalledWith("+12015550001"),
    );
    expect(await screen.findByText("12015550001")).toBeInTheDocument();
    expect(
      screen.getByRole("textbox", {
        name: "frontend.access_control.search_label",
      }),
    ).toBeInTheDocument();
  });

  it("filters phone identities by partial digits and excludes LID-only identities", async () => {
    const user = userEvent.setup();
    vi.mocked(listAccessBlocks).mockResolvedValue([
      block(1, { phone: "+58 (424) 123-4567" }),
      block(2),
      block(3, { phone: null, whatsapp_lid: "4241234567@lid" }),
    ]);

    render(<AccessControlSection />);

    expect(await screen.findByText("+58 (424) 123-4567")).toBeInTheDocument();
    expect(screen.getByText("4241234567@lid")).toBeInTheDocument();

    const search = screen.getByRole("textbox", {
      name: "frontend.access_control.search_label",
    });
    await user.type(search, "abc424 123");

    expect(search).toHaveValue("424 123");
    expect(screen.getByText("+58 (424) 123-4567")).toBeInTheDocument();
    expect(screen.queryByText("12015550002")).not.toBeInTheDocument();
    expect(screen.queryByText("4241234567@lid")).not.toBeInTheDocument();
  });

  it("paginates filtered results and resets to page one when the query changes", async () => {
    const user = userEvent.setup();
    vi.mocked(listAccessBlocks).mockResolvedValue([
      ...Array.from({ length: 12 }, (_, index) => block(index + 1)),
      block(13, { phone: "99999999999" }),
    ]);

    render(<AccessControlSection />);

    const search = await screen.findByRole("textbox", {
      name: "frontend.access_control.search_label",
    });
    await user.type(search, "1201");

    expect(
      screen.getByText("frontend.access_control.pagination_summary 1 10 12"),
    ).toBeInTheDocument();
    await user.click(
      screen.getByRole("button", {
        name: "frontend.access_control.pagination_page 2",
      }),
    );
    expect(screen.getByText("12015550011")).toBeInTheDocument();

    await user.clear(search);
    await user.type(search, "50001");

    expect(screen.getByText("12015550001")).toBeInTheDocument();
    expect(
      screen.queryByRole("button", {
        name: "frontend.access_control.pagination_page 2",
      }),
    ).not.toBeInTheDocument();
    expect(
      screen.getByText("frontend.access_control.pagination_summary 1 1 1"),
    ).toBeInTheDocument();
  });

  it("distinguishes no search results and clears from both available actions", async () => {
    const user = userEvent.setup();
    vi.mocked(listAccessBlocks).mockResolvedValue([block(1)]);

    render(<AccessControlSection />);

    const search = await screen.findByRole("textbox", {
      name: "frontend.access_control.search_label",
    });
    await user.type(search, "999");

    expect(
      screen.getByText("frontend.access_control.no_search_results"),
    ).toBeInTheDocument();
    const clearActions = screen.getAllByRole("button", {
      name: "frontend.access_control.clear_search",
    });
    expect(clearActions).toHaveLength(2);

    await user.click(clearActions[0]);
    expect(search).toHaveValue("");
    expect(screen.getByText("12015550001")).toBeInTheDocument();

    await user.type(search, "999");
    await user.click(
      screen.getAllByRole("button", {
        name: "frontend.access_control.clear_search",
      })[1],
    );
    expect(search).toHaveValue("");
    expect(screen.getByText("12015550001")).toBeInTheDocument();
  });

  it("preserves the query and clamps the filtered page after unblocking", async () => {
    const user = userEvent.setup();
    const initial = Array.from({ length: 11 }, (_, index) => block(index + 1));
    vi.mocked(listAccessBlocks)
      .mockResolvedValueOnce(initial)
      .mockResolvedValueOnce(initial.slice(0, 10));
    vi.mocked(deleteAccessBlock).mockResolvedValue(undefined);

    render(<AccessControlSection />);

    const search = await screen.findByRole("textbox", {
      name: "frontend.access_control.search_label",
    });
    await user.type(search, "1201555");
    await user.click(
      screen.getByRole("button", {
        name: "frontend.access_control.pagination_page 2",
      }),
    );
    expect(screen.getByText("12015550011")).toBeInTheDocument();

    await user.click(
      screen.getByRole("button", { name: "frontend.access_control.unblock" }),
    );

    await waitFor(() => expect(deleteAccessBlock).toHaveBeenCalledWith("block-11"));
    await waitFor(() => expect(screen.getByText("12015550001")).toBeInTheDocument());
    expect(
      screen.getByRole("textbox", {
        name: "frontend.access_control.search_label",
      }),
    ).toHaveValue("1201555");
    expect(
      screen.queryByRole("button", {
        name: "frontend.access_control.pagination_page 2",
      }),
    ).not.toBeInTheDocument();
  });

  it("preserves an active query after blocking and refreshing", async () => {
    const user = userEvent.setup();
    vi.mocked(listAccessBlocks)
      .mockResolvedValueOnce([block(1)])
      .mockResolvedValueOnce([
        block(2, { phone: "99912345678" }),
        block(1),
      ]);
    vi.mocked(createAccessBlock).mockResolvedValue(
      block(2, { phone: "99912345678" }),
    );

    render(<AccessControlSection />);

    const search = await screen.findByRole("textbox", {
      name: "frontend.access_control.search_label",
    });
    await user.type(search, "999");
    await user.type(
      screen.getByPlaceholderText("frontend.access_control.phone_placeholder"),
      "+99912345678",
    );
    await user.click(
      screen.getByRole("button", { name: "frontend.access_control.block" }),
    );

    expect(await screen.findByText("99912345678")).toBeInTheDocument();
    expect(
      screen.getByRole("textbox", {
        name: "frontend.access_control.search_label",
      }),
    ).toHaveValue("999");
    expect(screen.queryByText("12015550001")).not.toBeInTheDocument();
  });
});
