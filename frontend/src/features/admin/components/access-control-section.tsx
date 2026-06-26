import { useCallback, useEffect, useState } from "react";
import { toast } from "sonner";
import { Ban, Trash2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Badge } from "@/components/ui/badge";
import { t } from "@/i18n";
import {
  createAccessBlock,
  deleteAccessBlock,
  listAccessBlocks,
  type AccessControlBlock,
} from "../services/access-control-api";

function getApiError(error: unknown, fallback: string): string {
  const err = error as { response?: { data?: { detail?: string | Array<{ msg?: string }> } } };
  const detail = err.response?.data?.detail;
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail)) return detail.map((item) => item.msg || String(item)).join(", ");
  return error instanceof Error ? error.message : fallback;
}

export function AccessControlSection() {
  const [blocks, setBlocks] = useState<AccessControlBlock[]>([]);
  const [phone, setPhone] = useState("");
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      setBlocks(await listAccessBlocks());
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
    if (!phone.trim()) return;
    setSaving(true);
    try {
      await createAccessBlock(phone);
      setPhone("");
      await load();
      toast.success(t("frontend.access_control.saved"));
    } catch (error) {
      toast.error(getApiError(error, t("frontend.access_control.error_save")));
    } finally {
      setSaving(false);
    }
  }

  async function handleUnblock(id: string) {
    setSaving(true);
    try {
      await deleteAccessBlock(id);
      await load();
      toast.success(t("frontend.access_control.saved"));
    } catch (error) {
      toast.error(getApiError(error, t("frontend.access_control.error_save")));
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="flex flex-col gap-4">
      <form onSubmit={handleBlock} className="flex flex-col gap-3 sm:flex-row sm:items-end">
        <div className="flex flex-1 flex-col gap-2">
          <Label htmlFor="access-control-phone">{t("frontend.access_control.block")}</Label>
          <Input
            id="access-control-phone"
            value={phone}
            onChange={(event) => setPhone(event.target.value)}
            placeholder={t("frontend.access_control.phone_placeholder")}
          />
        </div>
        <Button type="submit" disabled={saving || !phone.trim()}>
          <Ban data-icon="inline-start" />
          {t("frontend.access_control.block")}
        </Button>
      </form>

      {loading ? (
        <div className="h-16 rounded-lg bg-muted" />
      ) : blocks.length === 0 ? (
        <p className="text-sm text-muted-foreground">{t("frontend.access_control.empty")}</p>
      ) : (
        <div className="flex flex-col gap-2">
          {blocks.map((block) => (
            <div key={block.id} className="flex items-center justify-between rounded-lg border p-3">
              <div className="flex items-center gap-2">
                <Badge variant="secondary">{block.phone || block.whatsapp_lid || "—"}</Badge>
              </div>
              <Button variant="ghost" size="sm" disabled={saving} onClick={() => handleUnblock(block.id)}>
                <Trash2 data-icon="inline-start" />
                {t("frontend.access_control.unblock")}
              </Button>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
