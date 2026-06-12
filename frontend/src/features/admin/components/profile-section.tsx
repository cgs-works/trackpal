import { useState, useEffect, useCallback } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
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
import {
  type Profile,
  type ProfileUpdate,
  updateProfile,
} from "../services/settings-api";
import { TimezonePicker } from "./timezone-picker";

const LOCALE_OPTIONS = [
  { value: "en", label: "English" },
  { value: "es", label: "Español" },
];

interface ProfileSectionProps {
  profile: Profile;
  onProfileUpdate: (profile: Profile) => void;
}

export function ProfileSection({ profile, onProfileUpdate }: ProfileSectionProps) {
  const {
    tenantSettings,
    timezoneOptions,
    loadTenantSettings,
    loadTimezoneOptions,
    updateTenantSettings,
  } = useSettingsStore();

  const [fullName, setFullName] = useState(profile.full_name || "");
  const [email, setEmail] = useState(profile.email || "");
  const [phone, setPhone] = useState(profile.phone || "");
  const [locale, setLocale] = useState(profile.locale || "en");
  const [timezone, setTimezone] = useState(profile.timezone || "UTC");
  const [saving, setSaving] = useState(false);

  const loadSettings = useCallback(async () => {
    await Promise.all([loadTenantSettings(), loadTimezoneOptions()]);
  }, [loadTenantSettings, loadTimezoneOptions]);

  useEffect(() => {
    loadSettings().catch(() => {
      toast.error(t("frontend.profile.error_update"));
    });
  }, [loadSettings]);

  useEffect(() => {
    setFullName(profile.full_name || "");
    setEmail(profile.email || "");
    setPhone(profile.phone || "");
    setLocale(tenantSettings?.locale || profile.locale || "en");
    setTimezone(tenantSettings?.timezone || profile.timezone || "UTC");
  }, [profile, tenantSettings]);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setSaving(true);
    try {
      const profilePayload: ProfileUpdate = {
        full_name: fullName || undefined,
        email: email || undefined,
        phone: phone || undefined,
      };
      const settingsPayload = {
        locale: locale || undefined,
        timezone: timezone || undefined,
      };
      const previousLocale = tenantSettings?.locale || profile.locale || "en";

      const [updatedProfile, updatedSettings] = await Promise.all([
        updateProfile(profilePayload),
        updateTenantSettings(settingsPayload),
      ]);

      onProfileUpdate({
        ...updatedProfile,
        locale: updatedSettings.locale,
        timezone: updatedSettings.timezone,
      });

      if (updatedSettings.locale !== previousLocale) {
        await loadCatalog();
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
    <form onSubmit={handleSubmit} className="space-y-4">
      <div className="grid sm:grid-cols-2 gap-4">
        <div className="space-y-2">
          <Label htmlFor="full_name">{t("frontend.profile.full_name")}</Label>
          <Input
            id="full_name"
            value={fullName}
            onChange={(e) => setFullName(e.target.value)}
          />
        </div>
        <div className="space-y-2">
          <Label htmlFor="email">{t("frontend.profile.email")}</Label>
          <Input
            id="email"
            type="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
          />
        </div>
      </div>

      <div className="grid sm:grid-cols-2 gap-4">
        <div className="space-y-2">
          <Label htmlFor="phone">{t("frontend.profile.phone")}</Label>
          <Input
            id="phone"
            type="tel"
            value={phone}
            onChange={(e) => setPhone(e.target.value)}
          />
        </div>
        <div className="space-y-2">
          <Label>{t("frontend.profile.language")}</Label>
          <Select value={locale} onValueChange={(v) => setLocale(v ?? "")}>
            <SelectTrigger>
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
      </div>

      <div className="space-y-2">
        <Label>{t("frontend.subscriptions.timezone")}</Label>
        <TimezonePicker
          value={timezone}
          onChange={(value) => setTimezone(value ?? "")}
          timezones={timezoneOptions}
        />
      </div>

      <div className="flex justify-end">
        <Button type="submit" disabled={saving}>
          {saving ? t("frontend.profile.saving") : t("frontend.profile.save")}
        </Button>
      </div>
    </form>
  );
}
