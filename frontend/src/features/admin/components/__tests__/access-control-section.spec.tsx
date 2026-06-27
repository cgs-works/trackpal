import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { AccessControlSection } from "../access-control-section";
import { createAccessBlock, deleteAccessBlock, listAccessBlocks } from "../../services/access-control-api";

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

function block(id: number) {
  return {
    id: `block-${id}`,
    tenant_id: "tenant-1",
    phone: `12015550${String(id).padStart(3, "0")}`,
    whatsapp_lid: null,
    created_at: "2026-06-27T00:00:00Z",
    updated_at: "2026-06-27T00:00:00Z",
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
    await user.type(screen.getByPlaceholderText("frontend.access_control.phone_placeholder"), "+12015550001");
    await user.click(screen.getByRole("button", { name: "frontend.access_control.block" }));

    await waitFor(() => expect(createAccessBlock).toHaveBeenCalledWith("+12015550001"));
    expect(await screen.findByText("12015550001")).toBeInTheDocument();
  });
});
