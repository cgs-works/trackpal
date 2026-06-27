import { useCallback, useEffect, useMemo, useState } from "react";
import { toast } from "sonner";
import { Copy, KeyRound, RefreshCw, Trash2 } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { Separator } from "@/components/ui/separator";
import { Skeleton } from "@/components/ui/skeleton";
import { t } from "@/i18n";
import { getApiError } from "@/lib/api-errors";
import { useSettingsStore } from "@/store/settings";

function splitOrigins(value: string): string[] {
  return value
    .split(/\r?\n/)
    .map((item) => item.trim())
    .filter(Boolean);
}

export function PublicApiSection() {
  const {
    publicApiKey,
    publicApiKeyLoaded,
    loadPublicApiKey,
    savePublicApiKeyOrigins,
    regeneratePublicApiKey,
    revokePublicApiKey,
  } = useSettingsStore();
  const [originsText, setOriginsText] = useState("");
  const [loading, setLoading] = useState(!publicApiKeyLoaded);
  const [saving, setSaving] = useState(false);
  const [regenerating, setRegenerating] = useState(false);
  const [revoking, setRevoking] = useState(false);

  const load = useCallback(async () => {
    if (publicApiKeyLoaded) {
      setOriginsText((publicApiKey?.allowed_origins || []).join("\n"));
      setLoading(false);
      return;
    }
    setLoading(true);
    try {
      const config = await loadPublicApiKey();
      setOriginsText((config?.allowed_origins || []).join("\n"));
    } catch (error) {
      toast.error(getApiError(error, t("frontend.public_api.error_load")));
    } finally {
      setLoading(false);
    }
  }, [loadPublicApiKey, publicApiKey, publicApiKeyLoaded]);

  useEffect(() => {
    load();
  }, [load]);

  const snippet = useMemo(() => {
    if (!publicApiKey?.api_key) return "";
    const baseUrl = import.meta.env.VITE_API_URL || "http://localhost:8000/api/v1";
    const url = `${baseUrl}/public/catalog?api_key=${publicApiKey.api_key}`;
    return `fetch("${url}")`;
  }, [publicApiKey?.api_key]);

  async function handleSave(event: React.FormEvent) {
    event.preventDefault();
    setSaving(true);
    try {
      const config = await savePublicApiKeyOrigins(splitOrigins(originsText));
      setOriginsText(config.allowed_origins.join("\n"));
      toast.success(t("frontend.public_api.saved"));
    } catch (error) {
      toast.error(getApiError(error, t("frontend.public_api.error_save")));
    } finally {
      setSaving(false);
    }
  }

  async function handleRegenerate() {
    setRegenerating(true);
    try {
      await regeneratePublicApiKey();
      toast.success(t("frontend.public_api.regenerated"));
    } catch (error) {
      toast.error(getApiError(error, t("frontend.public_api.error_regenerate")));
    } finally {
      setRegenerating(false);
    }
  }

  async function handleRevoke() {
    setRevoking(true);
    try {
      await revokePublicApiKey();
      setOriginsText("");
      toast.success(t("frontend.public_api.revoked"));
    } catch (error) {
      toast.error(getApiError(error, t("frontend.public_api.error_revoke")));
    } finally {
      setRevoking(false);
    }
  }

  async function handleCopy() {
    if (!publicApiKey?.api_key) return;
    try {
      await navigator.clipboard.writeText(publicApiKey.api_key);
      toast.success(t("frontend.public_api.copied"));
    } catch (error) {
      toast.error(getApiError(error, t("frontend.public_api.error_load")));
    }
  }

  if (loading) {
    return (
      <div className="flex flex-col gap-3">
        <Skeleton className="h-9 w-full" />
        <Skeleton className="h-24 w-full" />
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-4">
      <div className="flex flex-col gap-1">
        <h2 className="text-base font-medium">{t("frontend.public_api.section_title")}</h2>
        <p className="text-sm text-muted-foreground">{t("frontend.public_api.description")}</p>
      </div>

      <div className="flex flex-col gap-2 rounded-lg border bg-card p-3">
        <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
          <div className="flex min-w-0 items-center gap-2">
            <KeyRound className="size-4 text-muted-foreground" />
            {publicApiKey ? (
              <code className="truncate rounded bg-muted px-2 py-1 text-xs">{publicApiKey.api_key}</code>
            ) : (
              <span className="text-sm text-muted-foreground">{t("frontend.public_api.not_created")}</span>
            )}
          </div>
          <div className="flex flex-wrap gap-2">
            <Badge variant="secondary">{t("frontend.public_api.read_only")}</Badge>
            {publicApiKey && (
              <Button type="button" variant="outline" size="sm" onClick={handleCopy}>
                <Copy data-icon="inline-start" />
                {t("frontend.public_api.copy")}
              </Button>
            )}
          </div>
        </div>
      </div>

      <form onSubmit={handleSave} className="flex flex-col gap-3">
        <div className="flex flex-col gap-2">
          <Label htmlFor="public-api-origins">{t("frontend.public_api.origins_label")}</Label>
          <textarea
            id="public-api-origins"
            value={originsText}
            onChange={(event) => setOriginsText(event.target.value)}
            placeholder="https://example.com"
            aria-describedby="public-api-origins-help"
            className="min-h-24 w-full rounded-md border border-input bg-transparent px-3 py-2 text-sm shadow-xs outline-none transition-[color,box-shadow] placeholder:text-muted-foreground focus-visible:border-ring focus-visible:ring-ring/50 focus-visible:ring-[3px] disabled:cursor-not-allowed disabled:opacity-50"
          />
          <p id="public-api-origins-help" className="text-xs text-muted-foreground">
            {t("frontend.public_api.origins_help")}
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          <Button type="submit" disabled={saving}>
            {saving ? t("frontend.common.saving") : t("frontend.public_api.save")}
          </Button>
          <Button type="button" variant="outline" disabled={regenerating} onClick={handleRegenerate}>
            <RefreshCw data-icon="inline-start" />
            {t("frontend.public_api.regenerate")}
          </Button>
          <Button type="button" variant="destructive" disabled={!publicApiKey || revoking} onClick={handleRevoke}>
            <Trash2 data-icon="inline-start" />
            {t("frontend.public_api.revoke")}
          </Button>
        </div>
      </form>

      {snippet && (
        <>
          <Separator />
          <div className="flex flex-col gap-2">
            <Label>{t("frontend.public_api.example_title")}</Label>
            <code className="overflow-x-auto rounded-lg bg-muted p-3 text-xs text-muted-foreground">
              {snippet}
            </code>
          </div>
        </>
      )}
    </div>
  );
}
