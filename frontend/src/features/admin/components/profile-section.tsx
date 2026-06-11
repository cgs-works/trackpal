import { useState, useEffect } from "react";
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
import { type Profile, type ProfileUpdate, updateProfile } from "../services/settings-api";

const LOCALE_OPTIONS = [
  { value: "en", label: "English" },
  { value: "es", label: "Español" },
];

interface ProfileSectionProps {
  profile: Profile;
  onProfileUpdate: (profile: Profile) => void;
}

export function ProfileSection({ profile, onProfileUpdate }: ProfileSectionProps) {
  const [fullName, setFullName] = useState(profile.full_name || "");
  const [email, setEmail] = useState(profile.email || "");
  const [phone, setPhone] = useState(profile.phone || "");
  const [locale, setLocale] = useState(profile.locale || "en");
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    setFullName(profile.full_name || "");
    setEmail(profile.email || "");
    setPhone(profile.phone || "");
    setLocale(profile.locale || "en");
  }, [profile]);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setSaving(true);
    try {
      const payload: ProfileUpdate = {
        full_name: fullName || undefined,
        email: email || undefined,
        phone: phone || undefined,
        locale: locale || undefined,
      };
      const updated = await updateProfile(payload);
      onProfileUpdate(updated);
      toast.success("Profile updated");
    } catch (err) {
      toast.error(
        err instanceof Error ? err.message : "Failed to update profile"
      );
    } finally {
      setSaving(false);
    }
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-4">
      <div className="grid sm:grid-cols-2 gap-4">
        <div className="space-y-2">
          <Label htmlFor="full_name">Full Name</Label>
          <Input
            id="full_name"
            value={fullName}
            onChange={(e) => setFullName(e.target.value)}
          />
        </div>
        <div className="space-y-2">
          <Label htmlFor="email">Email</Label>
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
          <Label htmlFor="phone">Phone</Label>
          <Input
            id="phone"
            type="tel"
            value={phone}
            onChange={(e) => setPhone(e.target.value)}
          />
        </div>
        <div className="space-y-2">
          <Label>Locale</Label>
          <Select value={locale} onValueChange={setLocale}>
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

      <div className="flex justify-end">
        <Button type="submit" disabled={saving}>
          {saving ? "Saving..." : "Save Changes"}
        </Button>
      </div>
    </form>
  );
}
