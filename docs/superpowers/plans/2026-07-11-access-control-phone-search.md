# Access Control Phone Search Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add an accessible, localized Phone Search to Access Control that filters blocked phone identities before the existing client-side pagination.

**Architecture:** Keep the existing Access Control API unchanged: load the complete newest-first block collection, sanitize and normalize a local phone query, filter only records with a `phone`, then paginate the filtered collection in groups of ten. Keep all search state inside the mounted `AccessControlSection`, compose the UI from the installed shadcn `Input`, `Button`, and `Label` primitives, and test through the existing rendered component seam with only the API service mocked.

**Tech Stack:** React 19, TypeScript strict, Vitest 4, Testing Library, Tailwind CSS v4, shadcn/ui base-nova, Lucide React, FastAPI backend i18n catalogs, pytest.

## Global Constraints

- Use the domain term **Phone Search** for this lookup criterion.
- Phone Search matches blocked phone identities by a partial sequence of digits and does not match identities represented only by a WhatsApp LID.
- Accept digits plus common formatting characters (`+`, spaces, hyphens, and parentheses); reject letters and other characters from the controlled search value.
- Apply filtering immediately while the administrator types; do not add submit behavior or debounce.
- Preserve API-provided newest-first ordering; do not sort filtered results.
- Filter before paginating; keep the page size exactly `10`.
- Reset to page 1 when the normalized query changes, preserve the query across block/unblock refreshes, and clamp the page after a mutation if the filtered page count shrinks.
- Keep search state local to the mounted section so closing/reopening the Settings category resets it.
- Show Phone Search only after loading completes and at least one block exists.
- Distinguish the existing empty-block state from a filtered no-results state and provide both an in-field clear icon and a no-results clear action.
- All new visible and accessible copy must come from backend i18n catalogs in English and Spanish; do not hardcode translated strings.
- Preserve the existing REST API, database schema, authorization, plan gates, WhatsApp behavior, and service interfaces.
- Add no dependencies, global store, generic search framework, server-side search, or server-side pagination.
- Reuse semantic design tokens and installed shadcn variants; do not introduce raw colors, decorative motion, or custom theme rules.
- Preserve the existing `frontend/CONTEXT.md` Phone Search glossary entry created during specification.

---

## File Structure

- `backend/tests/test_i18n.py` — extend the existing Settings/frontend catalog contract test with all Phone Search keys.
- `backend/app/core/i18n/catalogs_en_frontend.py` — provide English Phone Search label, placeholder, clear action/name, and no-results copy.
- `backend/app/core/i18n/catalogs_es_frontend.py` — provide the matching Spanish copy.
- `frontend/src/features/admin/components/__tests__/access-control-section.spec.tsx` — describe all Phone Search behavior through rendered, accessible user interactions.
- `frontend/src/features/admin/components/access-control-section.tsx` — own local query state, sanitize input, filter phone blocks, paginate matches, render clear controls, and preserve mutation context.
- `frontend/CONTEXT.md` — retain the resolved implementation-free definition of Phone Search.
- `docs/codebase/frontend-components.md` — document the user-visible Access Control search/filter/pagination behavior.

No new production module is needed. The search logic is specific to `AccessControlSection`; extracting a reusable hook or store would add a seam without another consumer.

---

### Task 1: Localized Phone Search contract

**Files:**
- Modify: `backend/tests/test_i18n.py:446-481`
- Modify: `backend/app/core/i18n/catalogs_en_frontend.py:449-463`
- Modify: `backend/app/core/i18n/catalogs_es_frontend.py:449-463`

**Interfaces:**
- Consumes: `t(locale: str, key: str, **params) -> str` and the existing backend-sourced frontend catalog.
- Produces: four parameterless keys consumed by the React component: `frontend.access_control.search_label`, `frontend.access_control.search_placeholder`, `frontend.access_control.clear_search`, and `frontend.access_control.no_search_results`.

- [ ] **Step 1: Add the failing i18n contract assertions**

In `test_settings_frontend_i18n_keys_exist`, add the four Phone Search keys directly after the existing Access Control pagination keys in `keys_no_params`:

```python
        "frontend.access_control.pagination_previous",
        "frontend.access_control.pagination_next",
        "frontend.access_control.search_label",
        "frontend.access_control.search_placeholder",
        "frontend.access_control.clear_search",
        "frontend.access_control.no_search_results",
```

- [ ] **Step 2: Run the focused i18n test and verify RED**

Run:

```bash
cd backend && uv run pytest tests/test_i18n.py::test_settings_frontend_i18n_keys_exist -q
```

Expected: FAIL with `Missing i18n key 'frontend.access_control.search_label' in en catalog`. The failure must be a missing-key assertion, not an import, syntax, or fixture error.

- [ ] **Step 3: Add the English catalog values**

In the Access Control block of `catalogs_en_frontend.py`, insert these entries after `frontend.access_control.empty`:

```python
    "frontend.access_control.search_label": "Search phone",
    "frontend.access_control.search_placeholder": "Enter part of a phone number",
    "frontend.access_control.clear_search": "Clear search",
    "frontend.access_control.no_search_results": "No blocked phones match your search.",
```

The complete local sequence around the insertion must read:

```python
    "frontend.access_control.block": "Block phone",
    "frontend.access_control.unblock": "Unblock",
    "frontend.access_control.empty": "No blocked identities.",
    "frontend.access_control.search_label": "Search phone",
    "frontend.access_control.search_placeholder": "Enter part of a phone number",
    "frontend.access_control.clear_search": "Clear search",
    "frontend.access_control.no_search_results": "No blocked phones match your search.",
    "frontend.access_control.saved": "Access control updated.",
```

- [ ] **Step 4: Add the Spanish catalog values**

In the Access Control block of `catalogs_es_frontend.py`, insert:

```python
    "frontend.access_control.search_label": "Buscar teléfono",
    "frontend.access_control.search_placeholder": "Escribe parte de un teléfono",
    "frontend.access_control.clear_search": "Limpiar búsqueda",
    "frontend.access_control.no_search_results": "No hay teléfonos bloqueados que coincidan con tu búsqueda.",
```

The complete local sequence around the insertion must read:

```python
    "frontend.access_control.block": "Bloquear teléfono",
    "frontend.access_control.unblock": "Desbloquear",
    "frontend.access_control.empty": "No hay identidades bloqueadas.",
    "frontend.access_control.search_label": "Buscar teléfono",
    "frontend.access_control.search_placeholder": "Escribe parte de un teléfono",
    "frontend.access_control.clear_search": "Limpiar búsqueda",
    "frontend.access_control.no_search_results": "No hay teléfonos bloqueados que coincidan con tu búsqueda.",
    "frontend.access_control.saved": "Control de acceso actualizado.",
```

- [ ] **Step 5: Run the focused i18n test and verify GREEN**

Run:

```bash
cd backend && uv run pytest tests/test_i18n.py::test_settings_frontend_i18n_keys_exist -q
```

Expected: `1 passed` and exit code `0`.

- [ ] **Step 6: Commit the localized contract**

```bash
git add backend/tests/test_i18n.py backend/app/core/i18n/catalogs_en_frontend.py backend/app/core/i18n/catalogs_es_frontend.py
git commit -m "feat(access-control): add phone search copy"
```

---

### Task 2: Phone filtering, pagination, clearing, and mutation context

**Files:**
- Modify: `frontend/src/features/admin/components/__tests__/access-control-section.spec.tsx:1-101`
- Modify: `frontend/src/features/admin/components/access-control-section.tsx:1-131`
- Modify: `frontend/CONTEXT.md:116-117`
- Modify: `docs/codebase/frontend-components.md:88-90`

**Interfaces:**
- Consumes: `listAccessBlocks(): Promise<AccessControlBlock[]>`, `createAccessBlock(phone: string): Promise<AccessControlBlock>`, `deleteAccessBlock(id: string): Promise<void>`, and the four i18n keys from Task 1.
- Produces: `AccessControlSection(): JSX.Element` with local `phoneSearch: string`, partial digit matching over `AccessControlBlock.phone`, filtered pagination at `PAGE_SIZE = 10`, accessible clear actions, and preserved search state across list refreshes.
- Keeps unchanged: the public Access Control service interface and `AccessControlBlock` type.

- [ ] **Step 1: Make the test block factory support phone and LID scenarios**

Update the service import and replace the existing `block` helper with:

```tsx
import {
  createAccessBlock,
  deleteAccessBlock,
  listAccessBlocks,
  type AccessControlBlock,
} from "../../services/access-control-api";

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
```

Do not change the existing four pagination/mutation tests yet.

- [ ] **Step 2: Add a failing test for visibility, phone normalization, character rejection, and LID exclusion**

Append this test inside the existing `describe("AccessControlSection", ...)` block:

```tsx
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
```

This test exercises observable behavior only: the accessible field, its controlled value, and visible identities.

- [ ] **Step 3: Add a failing test that filtering precedes pagination and resets the page**

Append:

```tsx
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
    await user.type(search, "001");

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
```

- [ ] **Step 4: Add failing tests for both clear paths and empty-list visibility**

Append the no-results/clear behavior test:

```tsx
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
```

Then extend the existing `refreshes after blocking without breaking pagination` test with these assertions:

```tsx
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
```

Replace the corresponding old assertions in that test rather than duplicating the block form interaction.

- [ ] **Step 5: Add failing tests for query preservation and page clamping after mutations**

Append the unblock case:

```tsx
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
```

Append the block case:

```tsx
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
```

- [ ] **Step 6: Run the component tests and verify RED**

Run:

```bash
cd frontend && npm test -- --run src/features/admin/components/__tests__/access-control-section.spec.tsx
```

Expected: FAIL because no textbox named `frontend.access_control.search_label` exists. Existing pagination tests should remain green; the failures must come from the new Phone Search expectations.

- [ ] **Step 7: Replace `AccessControlSection` with the minimal implementation**

Replace `frontend/src/features/admin/components/access-control-section.tsx` with:

```tsx
import { useCallback, useEffect, useState } from "react";
import { toast } from "sonner";
import { Ban, Trash2, X } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { t } from "@/i18n";
import { getApiError } from "@/lib/api-errors";
import {
  createAccessBlock,
  deleteAccessBlock,
  listAccessBlocks,
  type AccessControlBlock,
} from "../services/access-control-api";

const PAGE_SIZE = 10;
const SEARCH_ALLOWED_CHARACTERS = /[^\d+()\-\s]/g;

function digitsOnly(value: string): string {
  return value.replace(/\D/g, "");
}

function filterBlocksByPhone(
  blocks: AccessControlBlock[],
  normalizedSearch: string,
): AccessControlBlock[] {
  if (!normalizedSearch) return blocks;
  return blocks.filter(
    (block) =>
      block.phone !== null &&
      digitsOnly(block.phone).includes(normalizedSearch),
  );
}

export function AccessControlSection() {
  const [blocks, setBlocks] = useState<AccessControlBlock[]>([]);
  const [phone, setPhone] = useState("");
  const [phoneSearch, setPhoneSearch] = useState("");
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [unblockingId, setUnblockingId] = useState<string | null>(null);
  const [page, setPage] = useState(1);
  const trimmedPhone = phone.trim();
  const normalizedSearch = digitsOnly(phoneSearch);
  const filteredBlocks = filterBlocksByPhone(blocks, normalizedSearch);
  const pageCount = Math.max(1, Math.ceil(filteredBlocks.length / PAGE_SIZE));
  const safePage = Math.min(page, pageCount);
  const pageStart = (safePage - 1) * PAGE_SIZE;
  const visibleBlocks = filteredBlocks.slice(pageStart, pageStart + PAGE_SIZE);
  const fromItem = filteredBlocks.length === 0 ? 0 : pageStart + 1;
  const toItem = Math.min(filteredBlocks.length, pageStart + PAGE_SIZE);

  const load = useCallback(async (): Promise<AccessControlBlock[] | null> => {
    setLoading(true);
    try {
      const nextBlocks = await listAccessBlocks();
      setBlocks(nextBlocks);
      return nextBlocks;
    } catch (error) {
      toast.error(getApiError(error, t("frontend.access_control.error_load")));
      return null;
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  function clampPage(nextBlocks: AccessControlBlock[]) {
    const nextFilteredCount = filterBlocksByPhone(
      nextBlocks,
      normalizedSearch,
    ).length;
    const nextPageCount = Math.max(1, Math.ceil(nextFilteredCount / PAGE_SIZE));
    setPage((current) => Math.min(current, nextPageCount));
  }

  function clearSearch() {
    setPhoneSearch("");
    setPage(1);
  }

  function handleSearchChange(value: string) {
    setPhoneSearch(value.replace(SEARCH_ALLOWED_CHARACTERS, ""));
    setPage(1);
  }

  async function handleBlock(e: React.FormEvent) {
    e.preventDefault();
    if (!trimmedPhone) return;
    setSaving(true);
    try {
      await createAccessBlock(trimmedPhone);
      setPhone("");
      const nextBlocks = await load();
      if (nextBlocks) clampPage(nextBlocks);
      toast.success(t("frontend.access_control.saved"));
    } catch (error) {
      toast.error(getApiError(error, t("frontend.access_control.error_save")));
    } finally {
      setSaving(false);
    }
  }

  async function handleUnblock(id: string) {
    setUnblockingId(id);
    try {
      await deleteAccessBlock(id);
      const nextBlocks = await load();
      if (nextBlocks) clampPage(nextBlocks);
      toast.success(t("frontend.access_control.saved"));
    } catch (error) {
      toast.error(getApiError(error, t("frontend.access_control.error_save")));
    } finally {
      setUnblockingId(null);
    }
  }

  return (
    <div className="flex flex-col gap-4">
      <form
        onSubmit={handleBlock}
        className="flex flex-col gap-3 sm:flex-row sm:items-end"
      >
        <div className="flex flex-1 flex-col gap-2">
          <Label htmlFor="access-control-phone">
            {t("frontend.access_control.block")}
          </Label>
          <Input
            id="access-control-phone"
            value={phone}
            onChange={(event) => setPhone(event.target.value)}
            placeholder={t("frontend.access_control.phone_placeholder")}
          />
        </div>
        <Button type="submit" disabled={saving || !trimmedPhone}>
          <Ban data-icon="inline-start" />
          {t("frontend.access_control.block")}
        </Button>
      </form>

      {loading ? (
        <div className="h-16 rounded-lg bg-muted" />
      ) : blocks.length === 0 ? (
        <p className="text-sm text-muted-foreground">
          {t("frontend.access_control.empty")}
        </p>
      ) : (
        <div className="flex flex-col gap-3">
          <div className="flex flex-col gap-2">
            <Label htmlFor="access-control-search">
              {t("frontend.access_control.search_label")}
            </Label>
            <div className="relative">
              <Input
                id="access-control-search"
                inputMode="tel"
                value={phoneSearch}
                onChange={(event) => handleSearchChange(event.target.value)}
                placeholder={t("frontend.access_control.search_placeholder")}
                className={phoneSearch ? "pr-9" : undefined}
              />
              {phoneSearch ? (
                <Button
                  type="button"
                  variant="ghost"
                  size="icon-xs"
                  aria-label={t("frontend.access_control.clear_search")}
                  title={t("frontend.access_control.clear_search")}
                  className="absolute end-1 top-1/2 -translate-y-1/2"
                  onClick={clearSearch}
                >
                  <X />
                </Button>
              ) : null}
            </div>
          </div>

          {filteredBlocks.length === 0 ? (
            <div className="flex flex-col items-start gap-2">
              <p className="text-sm text-muted-foreground">
                {t("frontend.access_control.no_search_results")}
              </p>
              <Button
                type="button"
                variant="outline"
                size="sm"
                onClick={clearSearch}
              >
                {t("frontend.access_control.clear_search")}
              </Button>
            </div>
          ) : (
            <>
              <p className="text-sm text-muted-foreground">
                {t("frontend.access_control.pagination_summary", {
                  from_item: fromItem,
                  to_item: toItem,
                  total: filteredBlocks.length,
                })}
              </p>
              <div className="flex flex-col gap-2">
                {visibleBlocks.map((block) => (
                  <div
                    key={block.id}
                    className="flex items-center justify-between gap-3 rounded-lg border p-3"
                  >
                    <Badge variant="secondary" className="min-w-0 truncate">
                      {block.phone || block.whatsapp_lid || "—"}
                    </Badge>
                    <Button
                      variant="ghost"
                      size="sm"
                      disabled={unblockingId === block.id}
                      onClick={() => void handleUnblock(block.id)}
                    >
                      <Trash2 data-icon="inline-start" />
                      {t("frontend.access_control.unblock")}
                    </Button>
                  </div>
                ))}
              </div>

              {pageCount > 1 ? (
                <div className="flex flex-wrap items-center gap-2">
                  <Button
                    type="button"
                    variant="outline"
                    size="sm"
                    disabled={safePage === 1}
                    onClick={() =>
                      setPage((current) => Math.max(1, current - 1))
                    }
                  >
                    {t("frontend.access_control.pagination_previous")}
                  </Button>
                  {Array.from(
                    { length: pageCount },
                    (_, index) => index + 1,
                  ).map((pageNumber) => (
                    <Button
                      key={pageNumber}
                      type="button"
                      variant={safePage === pageNumber ? "default" : "outline"}
                      size="sm"
                      aria-current={safePage === pageNumber ? "page" : undefined}
                      onClick={() => setPage(pageNumber)}
                    >
                      {t("frontend.access_control.pagination_page", {
                        page: pageNumber,
                      })}
                    </Button>
                  ))}
                  <Button
                    type="button"
                    variant="outline"
                    size="sm"
                    disabled={safePage === pageCount}
                    onClick={() =>
                      setPage((current) => Math.min(pageCount, current + 1))
                    }
                  >
                    {t("frontend.access_control.pagination_next")}
                  </Button>
                </div>
              ) : null}
            </>
          )}
        </div>
      )}
    </div>
  );
}
```

The helper functions remain module-private and feature-specific. `filterBlocksByPhone` uses `filter`, so it preserves API ordering. The clear icon uses the installed `Button` icon size and an accessible name; no custom icon sizing or new shadcn component is needed.

- [ ] **Step 8: Run the component test and verify GREEN**

Run:

```bash
cd frontend && npm test -- --run src/features/admin/components/__tests__/access-control-section.spec.tsx
```

Expected: all tests in `access-control-section.spec.tsx` PASS with exit code `0` and no React act warnings.

- [ ] **Step 9: Update behavior documentation**

Keep the existing `Phone Search` glossary row in `frontend/CONTEXT.md` exactly as:

```markdown
| **Phone Search** | Access Control lookup criterion that matches blocked phone identities by a partial sequence of digits. It does not match identities represented only by a WhatsApp LID. |
```

Replace the `AccessControlSection` paragraph in `docs/codebase/frontend-components.md` with:

```markdown
Lists active WhatsApp access blocks, blocks a phone, and unblocks existing entries through `/access-control/blocks`. This affects bot/code interactions only, not client portal accounts. Phone Search filters the already-loaded collection by partial phone digits, excludes LID-only identities while a query is active, and paginates matching results locally in groups of 10.
```

- [ ] **Step 10: Run focused cross-context verification**

Run:

```bash
cd backend && uv run pytest tests/test_i18n.py::test_settings_frontend_i18n_keys_exist -q
cd ../frontend && npm test -- --run src/features/admin/components/__tests__/access-control-section.spec.tsx src/features/admin/components/__tests__/settings-page.spec.tsx
```

Expected: the backend i18n test and both frontend component test files PASS. The Settings test proves that Access Control still mounts inside the existing category panel and is discarded on close.

- [ ] **Step 11: Run the complete frontend verification suite**

Run each command separately so a failure identifies its gate:

```bash
cd frontend && npm test -- --run
```

Expected: all Vitest files PASS with exit code `0`.

```bash
cd frontend && npm run lint
```

Expected: ESLint exits `0` with no errors.

```bash
cd frontend && npm run build
```

Expected: TypeScript project references compile and Vite production build exits `0`.

- [ ] **Step 12: Review the final diff for scope and accessibility**

Run:

```bash
git diff --check
git diff -- frontend/src/features/admin/components/access-control-section.tsx frontend/src/features/admin/components/__tests__/access-control-section.spec.tsx backend/app/core/i18n/catalogs_en_frontend.py backend/app/core/i18n/catalogs_es_frontend.py backend/tests/test_i18n.py frontend/CONTEXT.md docs/codebase/frontend-components.md
```

Expected: `git diff --check` prints nothing. Confirm from the diff that:

- the API service and `AccessControlBlock` type did not change;
- no translated string is hardcoded in JSX;
- the clear icon button has both `aria-label` and `title`;
- LID-only rows remain visible with an empty search and disappear only for a non-empty normalized phone query;
- filtering occurs before the `slice` used for pagination;
- no unrelated file is staged.

- [ ] **Step 13: Commit the Phone Search feature and docs**

```bash
git add frontend/src/features/admin/components/access-control-section.tsx frontend/src/features/admin/components/__tests__/access-control-section.spec.tsx frontend/CONTEXT.md docs/codebase/frontend-components.md
git commit -m "feat(access-control): add phone search"
```

---

## Final Acceptance Checklist

- [ ] Phone Search is absent during the true empty-list state and present for a loaded non-empty list.
- [ ] The accessible label is localized as “Search phone” / “Buscar teléfono”.
- [ ] Typing updates results immediately without a request, submit, or debounce.
- [ ] Common phone formatting is accepted, letters are removed, and matching compares partial digit sequences.
- [ ] LID-only identities remain in the unfiltered list and never match an active digit query.
- [ ] API-provided ordering remains unchanged.
- [ ] Filtered results, summary, numbered pages, Previous, and Next all use the filtered total with page size 10.
- [ ] Query changes reset to page 1.
- [ ] Both clear actions restore the full list and page 1.
- [ ] Block/unblock refreshes preserve the query and clamp an invalid page.
- [ ] Closing/reopening the Settings category resets local search state through component unmount/remount.
- [ ] No backend API, schema, authorization, plan-gate, service-interface, or WhatsApp behavior changed.
- [ ] English and Spanish catalogs contain all new copy.
- [ ] Focused tests, full frontend tests, lint, build, and diff checks pass with fresh output.
