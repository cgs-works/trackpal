import { useState, useEffect } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { toast } from "sonner";
import { t } from "@/i18n";
import {
  type Profile,
  type ProfileUpdate,
  updateProfile,
} from "../services/settings-api";

interface ProfileSectionProps {
  profile: Profile;
  onProfileUpdate: (profile: Profile) => void;
  onSave?: (payload: ProfileUpdate) => Promise<Profile>;
}

export function ProfileSection({ profile, onProfileUpdate, onSave }: ProfileSectionProps) {
  const [fullName, setFullName] = useState(profile.full_name || "");
  const [email, setEmail] = useState(profile.email || "");
  const [phone, setPhone] = useState(profile.phone || "");
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    setFullName(profile.full_name || "");
    setEmail(profile.email || "");
    setPhone(profile.phone || "");
  }, [profile]);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setSaving(true);
    try {
      const payload: ProfileUpdate = {
        full_name: fullName || undefined,
        email: email || undefined,
        phone: phone || undefined,
      };
      const updated = onSave ? await onSave(payload) : await updateProfile(payload);
      onProfileUpdate(updated);
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

      <div className="space-y-2">
        <Label htmlFor="phone">{t("frontend.profile.phone")}</Label>
        <Input
          id="phone"
          type="tel"
          value={phone}
          onChange={(e) => setPhone(e.target.value)}
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
