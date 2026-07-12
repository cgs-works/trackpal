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
