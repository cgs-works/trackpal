import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { toast } from "sonner";
import { changePassword } from "../services/settings-api";

export function PasswordSection() {
  const [oldPassword, setOldPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");

  const passwordsMatch = newPassword === confirmPassword || confirmPassword === "";
  const canSubmit = oldPassword && newPassword && passwordsMatch && newPassword.length >= 8;

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (newPassword !== confirmPassword) {
      setError("Passwords do not match");
      return;
    }
    setSaving(true);
    setError("");
    try {
      await changePassword({ old_password: oldPassword, new_password: newPassword });
      toast.success("Password updated");
      setOldPassword("");
      setNewPassword("");
      setConfirmPassword("");
    } catch (err) {
      setError(
        err instanceof Error ? err.message : "Failed to change password"
      );
    } finally {
      setSaving(false);
    }
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-4 max-w-md">
      {error && (
        <div className="rounded-lg bg-destructive/10 border border-destructive/20 p-3 text-sm text-destructive">
          {error}
        </div>
      )}

      <div className="space-y-2">
        <Label htmlFor="old_password">Current Password</Label>
        <Input
          id="old_password"
          type="password"
          autoComplete="current-password"
          required
          value={oldPassword}
          onChange={(e) => setOldPassword(e.target.value)}
        />
      </div>

      <div className="space-y-2">
        <Label htmlFor="new_password">New Password</Label>
        <Input
          id="new_password"
          type="password"
          autoComplete="new-password"
          required
          minLength={8}
          value={newPassword}
          onChange={(e) => setNewPassword(e.target.value)}
        />
        <p className="text-xs text-muted-foreground">
          Minimum 8 characters
        </p>
      </div>

      <div className="space-y-2">
        <Label htmlFor="confirm_password">Confirm New Password</Label>
        <Input
          id="confirm_password"
          type="password"
          autoComplete="new-password"
          required
          value={confirmPassword}
          onChange={(e) => setConfirmPassword(e.target.value)}
        />
        {!passwordsMatch && (
          <p className="text-xs text-destructive">Passwords do not match</p>
        )}
      </div>

      <div className="flex justify-end">
        <Button type="submit" disabled={saving || !canSubmit}>
          {saving ? "Changing..." : "Change Password"}
        </Button>
      </div>
    </form>
  );
}
