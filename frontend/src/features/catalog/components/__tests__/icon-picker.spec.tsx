import { render, screen, within, fireEvent } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, expect, it, vi } from "vitest";
import { IconPicker, type IconPickerProps } from "../icon-picker";

const search = vi.hoisted(() => vi.fn());
const describeIcon = vi.hoisted(() => vi.fn());
vi.mock("@/features/catalog/services/icon-catalog", () => ({
  iconifyCatalog: { search, describe: describeIcon },
}));
vi.mock("../service-icon", () => ({
  ServiceIcon: ({ icon, label }: { icon: string | null; label: string }) => (
    <span data-testid={`icon-${icon ?? "fallback"}`}>{label}</span>
  ),
}));
vi.mock("@/i18n", () => ({ t: (key: string) => key }));

const searchPageWithNetflix = {
  icons: ["simple-icons:netflix"],
  total: 1,
  limit: 64,
  start: 0,
  hasMore: false,
  collections: {
    "simple-icons": {
      prefix: "simple-icons",
      name: "Simple Icons",
      author: { name: "Simple Icons Collaborators", url: "https://simpleicons.org" },
      license: {
        title: "CC0 1.0",
        spdx: "CC0-1.0",
        url: "https://creativecommons.org/publicdomain/zero/1.0/",
      },
      palette: true,
    },
  },
};

function renderPicker(overrides: Partial<IconPickerProps> = {}) {
  const props: IconPickerProps = {
    open: true,
    value: null,
    initialQuery: "",
    onOpenChange: vi.fn(),
    onSelect: vi.fn(),
    ...overrides,
  };
  return { props, ...render(<IconPicker {...props} />) };
}

afterEach(() => {
  vi.useRealTimers();
  vi.clearAllMocks();
});

it("waits for two characters and debounces search by 300ms", async () => {
  vi.useFakeTimers();
  renderPicker();
  const input = screen.getByRole("searchbox");

  // Type "n" — only 1 char, should not trigger search
  fireEvent.change(input, { target: { value: "n" } });
  await vi.advanceTimersByTimeAsync(300);
  expect(search).not.toHaveBeenCalled();

  // Type "ne" — 2 chars, debounce should trigger after 300ms
  fireEvent.change(input, { target: { value: "ne" } });
  await vi.advanceTimersByTimeAsync(299);
  expect(search).not.toHaveBeenCalled();
  await vi.advanceTimersByTimeAsync(1);
  expect(search).toHaveBeenCalledWith("ne", 0, expect.any(AbortSignal));
});

it("shows collection license before enabling selection", async () => {
  search.mockResolvedValue(searchPageWithNetflix);
  renderPicker({ initialQuery: "netflix" });
  expect(await screen.findByText("CC0 1.0")).toBeInTheDocument();
  expect(screen.getByRole("link", { name: /CC0 1.0/ })).toHaveAttribute(
    "href",
    "https://creativecommons.org/publicdomain/zero/1.0/",
  );
  expect(screen.getByRole("button", { name: "frontend.icon_picker.select" })).toBeEnabled();
});

it("aborts an obsolete search when the query changes", async () => {
  vi.useFakeTimers();
  search.mockResolvedValue(searchPageWithNetflix);
  renderPicker();
  const input = screen.getByRole("searchbox");

  fireEvent.change(input, { target: { value: "ne" } });
  await vi.advanceTimersByTimeAsync(300);
  const firstSignal = search.mock.calls[0][2] as AbortSignal;

  fireEvent.change(input, { target: { value: "net" } });
  await vi.advanceTimersByTimeAsync(300);

  expect(firstSignal.aborted).toBe(true);
  expect(search).toHaveBeenLastCalledWith("net", 0, expect.any(AbortSignal));
});

it("shows an empty state for a successful search with no matches", async () => {
  search.mockResolvedValue({
    icons: [], total: 0, limit: 64, start: 0, hasMore: false, collections: {},
  });
  renderPicker({ initialQuery: "no-match" });
  expect(await screen.findByText("frontend.icon_picker.empty")).toBeInTheDocument();
});

it("keeps the current value when search fails and retries", async () => {
  describeIcon.mockResolvedValue({
    icon: "simple-icons:netflix",
    prefix: "simple-icons",
    name: "netflix",
    collection: searchPageWithNetflix.collections["simple-icons"],
  });
  search.mockRejectedValueOnce(new Error("offline")).mockResolvedValueOnce(searchPageWithNetflix);
  renderPicker({ value: "simple-icons:netflix", initialQuery: "netflix" });

  expect(await screen.findByText("frontend.icon_picker.error")).toBeInTheDocument();
  expect(screen.getByTestId("icon-simple-icons:netflix")).toBeInTheDocument();
  await userEvent.click(screen.getByRole("button", { name: "frontend.icon_picker.retry" }));
  expect(await screen.findByRole("option", { name: /simple-icons:netflix/ })).toBeInTheDocument();
});

it("loads and appends the next 64-result page", async () => {
  search
    .mockResolvedValueOnce({ ...searchPageWithNetflix, total: 65, hasMore: true })
    .mockResolvedValueOnce({
      icons: ["mdi:cloud"],
      total: 65,
      limit: 64,
      start: 64,
      hasMore: false,
      collections: {
        mdi: {
          prefix: "mdi",
          name: "Material Design Icons",
          author: { name: "Pictogrammers" },
          license: { title: "Apache 2.0", url: "https://www.apache.org/licenses/LICENSE-2.0" },
          palette: false,
        },
      },
    });
  renderPicker({ initialQuery: "cloud" });

  await screen.findByRole("option", { name: /simple-icons:netflix/ });
  await userEvent.click(screen.getByRole("button", { name: "frontend.icon_picker.load_more" }));

  expect(await screen.findByRole("option", { name: /mdi:cloud/ })).toBeInTheDocument();
  expect(search).toHaveBeenLastCalledWith("cloud", 64, expect.any(AbortSignal));
});

it("disables confirmation when license metadata is incomplete", async () => {
  search.mockResolvedValue({
    ...searchPageWithNetflix,
    collections: {
      "simple-icons": {
        ...searchPageWithNetflix.collections["simple-icons"],
        license: { title: "Unknown", url: "" },
      },
    },
  });
  renderPicker({ initialQuery: "netflix" });
  await userEvent.click(await screen.findByRole("option", { name: /simple-icons:netflix/ }));
  expect(screen.getByRole("button", { name: "frontend.icon_picker.select" })).toBeDisabled();
});

it("marks, confirms, and closes the selected icon", async () => {
  search.mockResolvedValue(searchPageWithNetflix);
  const { props } = renderPicker({ initialQuery: "netflix" });
  const option = await screen.findByRole("option", { name: /simple-icons:netflix/ });

  await userEvent.click(option);
  expect(option).toHaveAttribute("aria-selected", "true");
  expect(within(option).getByTestId("icon-picker-selected-marker")).toBeInTheDocument();
  await userEvent.click(screen.getByRole("button", { name: "frontend.icon_picker.select" }));

  expect(props.onSelect).toHaveBeenCalledWith("simple-icons:netflix");
  expect(props.onOpenChange).toHaveBeenCalledWith(false);
});

it("places the result grid before details for stacked mobile reading order", async () => {
  search.mockResolvedValue(searchPageWithNetflix);
  renderPicker({ initialQuery: "netflix" });
  const listbox = await screen.findByRole("listbox");
  const details = screen.getByTestId("icon-picker-details");
  expect(listbox.compareDocumentPosition(details) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
});
