import { useState, useEffect, useCallback } from "react";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { toast } from "sonner";
import { t } from "@/i18n";
import { useSettingsStore } from "@/store/settings";
import { TimezonePicker } from "./timezone-picker";

export function TimezoneSection() {
  const {
    tenantSettings,
    timezoneOptions,
    loadTenantSettings,
    loadTimezoneOptions,
    updateTenantSettings,
  } = useSettingsStore();

  const [timezone, setTimezone] = useState("UTC");
  const [saving, setSaving] = useState(false);

  const load = useCallback(async () => {
    await Promise.all([loadTenantSettings(), loadTimezoneOptions()]);
  }, [loadTenantSettings, loadTimezoneOptions]);

  useEffect(() => {
    load().catch(() => {});
  }, [load]);

  useEffect(() => {
    if (tenantSettings) {
      setTimezone(tenantSettings.timezone || "UTC");
    }
  }, [tenantSettings]);

  async function handleSave() {
    setSaving(true);
    try {
      await updateTenantSettings({ timezone });
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
        <Label>{t("frontend.subscriptions.timezone")}</Label>
        <TimezonePicker
          value={timezone}
          onChange={(value) => setTimezone(value ?? "UTC")}
          timezones={timezoneOptions}
        />
      </div>

      <div className="flex justify-end">
        <Button onClick={handleSave} disabled={saving}>
          {saving ? t("frontend.profile.saving") : t("frontend.profile.save")}
        </Button>
      </div>
    </div>
  );
}
