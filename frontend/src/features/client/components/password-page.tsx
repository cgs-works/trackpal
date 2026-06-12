import { useState } from "react";
import { useAuthStore } from "@/store/auth";
import { Navigate } from "@tanstack/react-router";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { toast } from "sonner";
import { Shield } from "lucide-react";
import { t } from "@/i18n";
import { changePassword } from "../services/client-dashboard-api";

export function PasswordPage() {
  const { isAuthenticated, role } = useAuthStore();

  const [oldPassword, setOldPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");

  const passwordsMatch = newPassword === confirmPassword || confirmPassword === "";
  const canSubmit = oldPassword && newPassword && passwordsMatch && newPassword.length >= 8;

  if (!isAuthenticated || role !== "client") {
    return <Navigate to="/login" replace />;
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (newPassword !== confirmPassword) {
      setError(t("frontend.profile.passwords_dont_match"));
      return;
    }
    setSaving(true);
    setError("");
    try {
      await changePassword({ old_password: oldPassword, new_password: newPassword });
      toast.success(t("frontend.dashboard.client.password_updated"));
      setOldPassword("");
      setNewPassword("");
      setConfirmPassword("");
    } catch (err) {
      setError(
        err instanceof Error ? err.message : t("frontend.dashboard.client.error_password")
      );
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="flex-1 overflow-auto">
      <div className="max-w-5xl mx-auto px-4 sm:px-6 py-6 flex flex-col gap-6">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">
            {t("frontend.dashboard.client.security")}
          </h1>
          <p className="text-muted-foreground">
            {t("frontend.dashboard.client.change_password")}
          </p>
        </div>

        <Card className="max-w-lg">
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-base">
              <Shield className="size-5 text-muted-foreground" />
              {t("frontend.dashboard.client.change_password")}
            </CardTitle>
          </CardHeader>
          <CardContent>
            <form onSubmit={handleSubmit} className="space-y-4">
              {error && (
                <div className="rounded-lg bg-destructive/10 border border-destructive/20 p-3 text-sm text-destructive">
                  {error}
                </div>
              )}

              <div className="space-y-2">
                <Label htmlFor="old_password">
                  {t("frontend.dashboard.client.current_password")}
                </Label>
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
                <Label htmlFor="new_password">
                  {t("frontend.dashboard.client.new_password")}
                </Label>
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
                  {t("frontend.profile.password_min_length")}
                </p>
              </div>

              <div className="space-y-2">
                <Label htmlFor="confirm_password">
                  {t("frontend.profile.confirm_password")}
                </Label>
                <Input
                  id="confirm_password"
                  type="password"
                  autoComplete="new-password"
                  required
                  value={confirmPassword}
                  onChange={(e) => setConfirmPassword(e.target.value)}
                />
                {!passwordsMatch && (
                  <p className="text-xs text-destructive">
                    {t("frontend.profile.passwords_dont_match")}
                  </p>
                )}
              </div>

              <div className="flex justify-end">
                <Button type="submit" disabled={saving || !canSubmit}>
                  {saving
                    ? t("frontend.dashboard.client.updating")
                    : t("frontend.dashboard.client.update_password")}
                </Button>
              </div>
            </form>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
