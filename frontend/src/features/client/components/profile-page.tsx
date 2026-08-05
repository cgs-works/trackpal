import { useState, useEffect, useCallback } from "react";
import { useAuthStore } from "@/store/auth";
import { Navigate } from "@tanstack/react-router";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Skeleton } from "@/components/ui/skeleton";
import {
  User,
  Mail,
  Phone,
  Building2,
  Shield,
  AlertCircle,
} from "lucide-react";
import { t } from "@/i18n";
import { HELP_TARGETS } from "@/features/help/help-targets";
import {
  getProfile,
  changePassword,
  type ClientProfile,
} from "../services/client-dashboard-api";

/* ── Status Badge ──────────────────────────────────────────── */

function StatusBadge({ active }: { active: boolean }) {
  return (
    <Badge
      variant={active ? "default" : "secondary"}
      className={
        active
          ? "bg-emerald-100 text-emerald-800 hover:bg-emerald-100 dark:bg-emerald-900 dark:text-emerald-300"
          : "bg-amber-100 text-amber-800 hover:bg-amber-100 dark:bg-amber-900 dark:text-amber-300"
      }
    >
      {t(active ? "frontend.dashboard.client.status_active" : "frontend.dashboard.client.status_inactive")}
    </Badge>
  );
}

/* ── Profile Page ──────────────────────────────────────────── */

export function ProfilePage() {
  const { isAuthenticated, role } = useAuthStore();

  const [profile, setProfile] = useState<ClientProfile | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState("");

  // Password form state
  const [oldPassword, setOldPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [saving, setSaving] = useState(false);
  const [passwordError, setPasswordError] = useState("");
  const [passwordSuccess, setPasswordSuccess] = useState(false);

  const loadProfile = useCallback(async () => {
    setIsLoading(true);
    setError("");
    try {
      const data = await getProfile();
      setProfile(data);
    } catch (err) {
      setError(
        err instanceof Error ? err.message : t("frontend.profile.load_error")
      );
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    loadProfile();
  }, [loadProfile]);

  if (!isAuthenticated || role !== "client") {
    return <Navigate to="/login" replace />;
  }

  const passwordsMatch = newPassword === confirmPassword || confirmPassword === "";
  const canSubmitPassword = oldPassword && newPassword && passwordsMatch && newPassword.length >= 8;

  async function handlePasswordSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (newPassword !== confirmPassword) {
      setPasswordError(t("frontend.profile.passwords_dont_match"));
      return;
    }
    setSaving(true);
    setPasswordError("");
    setPasswordSuccess(false);
    try {
      await changePassword({ old_password: oldPassword, new_password: newPassword });
      setPasswordSuccess(true);
      setOldPassword("");
      setNewPassword("");
      setConfirmPassword("");
    } catch (err) {
      setPasswordError(
        err instanceof Error ? err.message : t("frontend.dashboard.client.error_password")
      );
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="flex-1 overflow-auto">
      <div className="max-w-5xl mx-auto px-4 sm:px-6 py-6 flex flex-col gap-6">
        {/* ── Loading state ─────────────────────────────────── */}
        {isLoading && (
          <>
            <div className="space-y-2">
              <Skeleton className="h-8 w-48" />
              <Skeleton className="h-4 w-64" />
            </div>
            <Skeleton className="h-64 rounded-xl" />
            <Skeleton className="h-80 rounded-xl" />
          </>
        )}

        {/* ── Error state ───────────────────────────────────── */}
        {!isLoading && error && (
          <div className="rounded-lg bg-destructive/10 border border-destructive/20 p-4 text-sm text-destructive flex items-start gap-3">
            <AlertCircle className="size-4 mt-0.5 shrink-0" />
            <div>
              <p className="font-medium">
                {t("frontend.profile.load_error")}
              </p>
              <p className="mt-1">{error}</p>
              <Button
                variant="outline"
                size="sm"
                className="mt-3"
                onClick={loadProfile}
              >
                {t("frontend.common.retry")}
              </Button>
            </div>
          </div>
        )}

        {/* ── Content ───────────────────────────────────────── */}
        {!isLoading && !error && profile && (
          <>
            {/* Header */}
            <div>
              <h1 className="text-2xl font-bold tracking-tight">
                {t("frontend.dashboard.client.profile")}
              </h1>
              <p className="text-muted-foreground">
                {t("frontend.dashboard.client.view_profile")}
              </p>
            </div>

            {/* Profile Information Card */}
            <Card data-help-id={HELP_TARGETS.clientProfile}>
              <CardHeader>
                <CardTitle className="flex items-center gap-2 text-base">
                  <User className="size-5 text-muted-foreground" />
                  {t("frontend.dashboard.client.profile_info")}
                </CardTitle>
              </CardHeader>
              <CardContent className="space-y-4">
                {/* Full Name */}
                <div className="flex flex-col sm:flex-row sm:items-center gap-1 sm:gap-4">
                  <span className="text-sm text-muted-foreground w-32 shrink-0">
                    {t("frontend.dashboard.client.full_name")}
                  </span>
                  <span className="text-sm font-medium">
                    {profile.full_name || "—"}
                  </span>
                </div>

                {/* Username */}
                <div className="flex flex-col sm:flex-row sm:items-center gap-1 sm:gap-4">
                  <span className="text-sm text-muted-foreground w-32 shrink-0">
                    {t("frontend.dashboard.client.username")}
                  </span>
                  <div className="flex items-center gap-2">
                    <Mail className="size-4 text-muted-foreground" />
                    <span className="text-sm font-medium">
                      {profile.username}
                    </span>
                  </div>
                </div>

                {/* Phone */}
                {profile.phone && (
                  <div className="flex flex-col sm:flex-row sm:items-center gap-1 sm:gap-4">
                    <span className="text-sm text-muted-foreground w-32 shrink-0">
                      {t("frontend.dashboard.client.phone")}
                    </span>
                    <div className="flex items-center gap-2">
                      <Phone className="size-4 text-muted-foreground" />
                      <span className="text-sm font-medium">
                        {profile.phone}
                      </span>
                    </div>
                  </div>
                )}

                {/* Provider */}
                <div className="flex flex-col sm:flex-row sm:items-center gap-1 sm:gap-4">
                  <span className="text-sm text-muted-foreground w-32 shrink-0">
                    {t("frontend.dashboard.client.provider")}
                  </span>
                  <div className="flex items-center gap-2">
                    <Building2 className="size-4 text-muted-foreground" />
                    <span className="text-sm font-medium">
                      {profile.tenant_name || "—"}
                    </span>
                  </div>
                </div>

                {/* Status */}
                <div className="flex flex-col sm:flex-row sm:items-center gap-1 sm:gap-4">
                  <span className="text-sm text-muted-foreground w-32 shrink-0">
                    {t("frontend.dashboard.client.status")}
                  </span>
                  <StatusBadge active={profile.is_active ?? false} />
                </div>
              </CardContent>
            </Card>

            {/* Password Change Card */}
            <Card data-help-id={HELP_TARGETS.clientPassword}>
              <CardHeader>
                <CardTitle className="flex items-center gap-2 text-base">
                  <Shield className="size-5 text-muted-foreground" />
                  {t("frontend.dashboard.client.change_password")}
                </CardTitle>
              </CardHeader>
              <CardContent>
                <form onSubmit={handlePasswordSubmit} className="space-y-4 max-w-lg">
                  {passwordError && (
                    <div className="rounded-lg bg-destructive/10 border border-destructive/20 p-3 text-sm text-destructive">
                      {passwordError}
                    </div>
                  )}

                  {passwordSuccess && (
                    <div className="rounded-lg bg-emerald-50 border border-emerald-200 p-3 text-sm text-emerald-800 dark:bg-emerald-900/30 dark:border-emerald-800 dark:text-emerald-300">
                      {t("frontend.dashboard.client.password_updated")}
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
                    <Button type="submit" disabled={saving || !canSubmitPassword}>
                      {saving
                        ? t("frontend.dashboard.client.updating")
                        : t("frontend.dashboard.client.update_password")}
                    </Button>
                  </div>
                </form>
              </CardContent>
            </Card>
          </>
        )}
      </div>
    </div>
  );
}
