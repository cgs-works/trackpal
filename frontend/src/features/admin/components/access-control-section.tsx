import { useCallback, useEffect, useMemo, useState } from "react";
import { toast } from "sonner";
import { Ban, Trash2 } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { t } from "@/i18n";
import { getApiError } from "@/lib/api-errors";
import { createAccessBlock, deleteAccessBlock, listAccessBlocks, type AccessControlBlock } from "../services/access-control-api";

const PAGE_SIZE = 10;

export function AccessControlSection() {
  const [blocks, setBlocks] = useState<AccessControlBlock[]>([]);
  const [phone, setPhone] = useState("");
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [unblockingId, setUnblockingId] = useState<string | null>(null);
  const [page, setPage] = useState(1);
  const trimmedPhone = phone.trim();
  const pageCount = Math.max(1, Math.ceil(blocks.length / PAGE_SIZE));
  const safePage = Math.min(page, pageCount);
  const visibleBlocks = useMemo(() => {
    const start = (safePage - 1) * PAGE_SIZE;
    return blocks.slice(start, start + PAGE_SIZE);
  }, [blocks, safePage]);
  const fromItem = blocks.length === 0 ? 0 : (safePage - 1) * PAGE_SIZE + 1;
  const toItem = Math.min(blocks.length, safePage * PAGE_SIZE);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const nextBlocks = await listAccessBlocks();
      setBlocks(nextBlocks);
      setPage((current) => Math.min(current, Math.max(1, Math.ceil(nextBlocks.length / PAGE_SIZE))));
    } catch (error) {
      toast.error(getApiError(error, t("frontend.access_control.error_load")));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  async function handleBlock(e: React.FormEvent) {
    e.preventDefault();
    if (!trimmedPhone) return;
    setSaving(true);
    try {
      await createAccessBlock(trimmedPhone);
      setPhone("");
      setPage(1);
      await load();
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
      await load();
      toast.success(t("frontend.access_control.saved"));
    } catch (error) {
      toast.error(getApiError(error, t("frontend.access_control.error_save")));
    } finally {
      setUnblockingId(null);
    }
  }

  return (
    <div className="flex flex-col gap-4">
      <form onSubmit={handleBlock} className="flex flex-col gap-3 sm:flex-row sm:items-end">
        <div className="flex flex-1 flex-col gap-2">
          <Label htmlFor="access-control-phone">{t("frontend.access_control.block")}</Label>
          <Input id="access-control-phone" value={phone} onChange={(event) => setPhone(event.target.value)} placeholder={t("frontend.access_control.phone_placeholder")} />
        </div>
        <Button type="submit" disabled={saving || !trimmedPhone}>
          <Ban data-icon="inline-start" />
          {t("frontend.access_control.block")}
        </Button>
      </form>

      {loading ? (
        <div className="h-16 rounded-lg bg-muted" />
      ) : blocks.length === 0 ? (
        <p className="text-sm text-muted-foreground">{t("frontend.access_control.empty")}</p>
      ) : (
        <div className="flex flex-col gap-3">
          <p className="text-sm text-muted-foreground">
            {t("frontend.access_control.pagination_summary", { from_item: fromItem, to_item: toItem, total: blocks.length })}
          </p>
          <div className="flex flex-col gap-2">
            {visibleBlocks.map((block) => (
              <div key={block.id} className="flex items-center justify-between gap-3 rounded-lg border p-3">
                <Badge variant="secondary" className="min-w-0 truncate">
                  {block.phone || block.whatsapp_lid || "—"}
                </Badge>
                <Button variant="ghost" size="sm" disabled={unblockingId === block.id} onClick={() => void handleUnblock(block.id)}>
                  <Trash2 data-icon="inline-start" />
                  {t("frontend.access_control.unblock")}
                </Button>
              </div>
            ))}
          </div>

          {pageCount > 1 && (
            <div className="flex flex-wrap items-center gap-2">
              <Button type="button" variant="outline" size="sm" disabled={safePage === 1} onClick={() => setPage((current) => Math.max(1, current - 1))}>
                {t("frontend.access_control.pagination_previous")}
              </Button>
              {Array.from({ length: pageCount }, (_, index) => index + 1).map((pageNumber) => (
                <Button key={pageNumber} type="button" variant={safePage === pageNumber ? "default" : "outline"} size="sm" aria-current={safePage === pageNumber ? "page" : undefined} onClick={() => setPage(pageNumber)}>
                  {t("frontend.access_control.pagination_page", { page: pageNumber })}
                </Button>
              ))}
              <Button type="button" variant="outline" size="sm" disabled={safePage === pageCount} onClick={() => setPage((current) => Math.min(pageCount, current + 1))}>
                {t("frontend.access_control.pagination_next")}
              </Button>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
