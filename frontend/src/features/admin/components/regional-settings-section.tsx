import { useState, useEffect, useCallback } from "react";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
} from "@/components/ui/select";
import { toast } from "sonner";
import { t, loadCatalog } from "@/i18n";
import { useSettingsStore } from "@/store/settings";
import { useAuthStore } from "@/store/auth";
import { CountryPicker } from "./country-picker";
import { CurrencyPicker } from "./currency-picker";
import { TimezonePicker } from "./timezone-picker";

const LOCALE_OPTIONS = [
  { value: "en", label: "English" },
  { value: "es", label: "Español" },
];

export function RegionalSettingsSection() {
  const { role, tenantPlan, isMasterSupportContext, dataSource } = useAuthStore();
  const {
    tenantSettings,
    timezoneOptions,
    currencyOptions,
    loadTenantSettings,
    loadTimezoneOptions,
    loadCurrencyOptions,
    updateTenantSettings,
  } = useSettingsStore();

  const isStarterTenantAdmin = role === "tenant" && tenantPlan === "starter";
  const showProFields = !isStarterTenantAdmin || isMasterSupportContext;

  const [country, setCountry] = useState<string | null>(null);
  const [locale, setLocale] = useState("en");
  const [timezone, setTimezone] = useState("UTC");
  const [currency, setCurrency] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

  const load = useCallback(async () => {
    await Promise.all([
      loadTenantSettings(dataSource.settings),
      loadTimezoneOptions(dataSource.settings),
      loadCurrencyOptions(dataSource.settings),
    ]);
  }, [dataSource.settings, loadTenantSettings, loadTimezoneOptions, loadCurrencyOptions]);

  useEffect(() => {
    load().catch(() => {});
  }, [load]);

  useEffect(() => {
    if (tenantSettings) {
      setCountry(tenantSettings.country || null);
      setLocale(tenantSettings.locale || "en");
      setTimezone(tenantSettings.timezone || "UTC");
      setCurrency(tenantSettings.currency || null);
    }
  }, [tenantSettings]);

  const officialCurrency = country
    ? (currencyOptions?.countries.find((c) => c.code === country)?.currency ?? null)
    : null;

  async function handleSave() {
    setSaving(true);
    try {
      const prev = tenantSettings?.locale || "en";
      const payload: { country?: string; locale: string; timezone?: string; currency?: string } = {
        country: country ?? undefined,
        locale,
      };
      if (showProFields) {
        payload.timezone = timezone;
        payload.currency = currency ?? undefined;
      }
      await updateTenantSettings(payload, dataSource.settings);
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

  const localeLabel = LOCALE_OPTIONS.find((option) => option.value === locale)?.label ?? locale;

  return (
    <div className="space-y-6" data-help-id="admin.settings.regional">
      {/* Country */}
      <div className="space-y-2">
        <Label>{t("frontend.my_account.regional.country")}</Label>
        <CountryPicker
          value={country}
          countries={currencyOptions?.countries ?? []}
          onChange={setCountry}
        />
      </div>

      {/* Language */}
      <div className="space-y-2">
        <Label>{t("frontend.profile.language")}</Label>
        <Select value={locale} onValueChange={(v) => setLocale(v ?? "en")}>
          <SelectTrigger className="w-48">
            <span data-slot="select-value">{localeLabel}</span>
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

      {/* Timezone — Pro only */}
      {showProFields && (
        <div className="space-y-2">
          <Label>{t("frontend.subscriptions.timezone")}</Label>
          <TimezonePicker
            value={timezone}
            onChange={(value) => setTimezone(value ?? "UTC")}
            timezones={timezoneOptions}
          />
        </div>
      )}

      {/* Currency — Pro only */}
      {showProFields && (
        <div className="space-y-2">
          <Label>{t("frontend.my_account.regional.currency")}</Label>
          <CurrencyPicker
            value={currency}
            currencies={currencyOptions?.currencies ?? []}
            officialCurrency={officialCurrency}
            onChange={setCurrency}
          />
        </div>
      )}

      <div className="flex justify-end">
        <Button onClick={handleSave} disabled={saving}>
          {saving ? t("frontend.profile.saving") : t("frontend.profile.save")}
        </Button>
      </div>
    </div>
  );
}
