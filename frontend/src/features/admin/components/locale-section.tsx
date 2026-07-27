import { useState, useEffect, useCallback } from "react";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { toast } from "sonner";
import { t, loadCatalog } from "@/i18n";
import { useSettingsStore } from "@/store/settings";
import { useAuthStore } from "@/store/auth";

const LOCALE_OPTIONS = [
  { value: "en", label: "English" },
  { value: "es", label: "Español" },
];

export function LocaleSection() {
  const { dataSource } = useAuthStore();
  const { tenantSettings, loadTenantSettings, updateTenantSettings } =
    useSettingsStore();

  const [locale, setLocale] = useState("en");
  const [saving, setSaving] = useState(false);

  const load = useCallback(async () => {
    await loadTenantSettings(dataSource.settings);
  }, [dataSource.settings, loadTenantSettings]);

  useEffect(() => {
    load().catch(() => {});
  }, [load]);

  useEffect(() => {
    if (tenantSettings) {
      setLocale(tenantSettings.locale || "en");
    }
  }, [tenantSettings]);

  async function handleSave() {
    setSaving(true);
    try {
      const prev = tenantSettings?.locale || "en";
      await updateTenantSettings({ locale }, dataSource.settings);
      if (locale !== prev) {
        await loadCatalog(dataSource.mode === "demo" ? locale : undefined);
      }
      toast.success(t("frontend.profile.saved"));
    } catch (err) {
      toast.error(
        err instanceof Error ? err.message : t("frontend.profile.error_update")
      );
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="space-y-4">
      <div className="space-y-2">
        <Label>{t("frontend.profile.language")}</Label>
        <Select value={locale} onValueChange={(v) => setLocale(v ?? "en")}>
          <SelectTrigger className="w-48">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            {LOCALE_OPTIONS.map((opt) => (
              <SelectItem key={opt.value} value={opt.value}>
                {opt.label}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>

      <div className="flex justify-end">
        <Button onClick={handleSave} disabled={saving}>
          {saving ? t("frontend.profile.saving") : t("frontend.profile.save")}
        </Button>
      </div>
    </div>
  );
}
