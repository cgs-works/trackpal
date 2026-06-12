import { useState, useEffect, useCallback } from "react";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectGroup,
  SelectLabel,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Separator } from "@/components/ui/separator";
import { Skeleton } from "@/components/ui/skeleton";
import { Alert } from "@/components/ui/alert";
import { X, Plus, AlertCircle } from "lucide-react";
import { toast } from "sonner";
import { t } from "@/i18n";
import {
  getReminderSettings,
  updateReminderSettings,
  getTimezones,
  type TimezoneOption,
} from "../services/reminder-api";

// ── Placeholder values for preview ──────────────────────────────
const PREVIEW_PLACEHOLDERS = {
  client_name: "María García",
  service_name: "Netflix Premium",
  days: "7",
  streaming_email: "user@example.com",
  expires_at: "2026-07-15",
};

// ── Default messages ────────────────────────────────────────────
const DEFAULT_TENANT_MESSAGE =
  "Recordatorio: La suscripción de {{client_name}} para {{service_name}} vence en {{days}} días. Email: {{streaming_email}}.";
const DEFAULT_CLIENT_MESSAGE =
  "Hola {{client_name}}, tu suscripción a {{service_name}} vence en {{days}} días. Renueva para continuar disfrutando del servicio.";

// ── Timezone groups ─────────────────────────────────────────────
function groupTimezones(timezones: TimezoneOption[]) {
  const groups: Record<string, TimezoneOption[]> = {};
  for (const tz of timezones) {
    const group = tz.group || "Other";
    if (!groups[group]) groups[group] = [];
    groups[group].push(tz);
  }
  return groups;
}

// ── Preview renderer ────────────────────────────────────────────
function renderPreview(template: string): string {
  let result = template;
  for (const [key, value] of Object.entries(PREVIEW_PLACEHOLDERS)) {
    result = result.replace(new RegExp(`\\{\\{${key}\\}\\}`, "g"), value);
  }
  return result;
}

// ── Component ───────────────────────────────────────────────────
interface ReminderSettingsModalProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

export function ReminderSettingsModal({
  open,
  onOpenChange,
}: ReminderSettingsModalProps) {
  const [isLoading, setIsLoading] = useState(true);
  const [isSaving, setIsSaving] = useState(false);
  const [error, setError] = useState("");
  const [timezones, setTimezones] = useState<TimezoneOption[]>([]);

  const [settings, setSettings] = useState({
    reminders_enabled: false,
    timezone: "UTC",
    warning_days: [7, 3, 1] as number[],
    reminder_time: "09:00",
    recipient_mode: "tenant_only" as "tenant_only" | "client_only" | "both",
    custom_message_tenant: null as string | null,
    custom_message_client: null as string | null,
  });

  const [customDay, setCustomDay] = useState("");
  const [validationErrors, setValidationErrors] = useState<
    Record<string, string>
  >({});

  // ── Load data ───────────────────────────────────────────────
  const loadData = useCallback(async () => {
    if (!open) return;
    setError("");
    setIsLoading(true);

    try {
      const [settingsData, timezonesData] = await Promise.all([
        getReminderSettings(),
        getTimezones(),
      ]);

      setSettings({
        reminders_enabled: settingsData.reminders_enabled,
        timezone: settingsData.timezone || "UTC",
        warning_days: settingsData.warning_days || [7, 3, 1],
        reminder_time: settingsData.reminder_time || "09:00",
        recipient_mode: settingsData.recipient_mode || "tenant_only",
        custom_message_tenant: settingsData.custom_message_tenant,
        custom_message_client: settingsData.custom_message_client,
      });
      setTimezones(timezonesData);
    } catch (err: unknown) {
      const apiErr = err as {
        response?: { data?: { detail?: string | Array<{ msg?: string }> } }
      };
      const detail = apiErr.response?.data?.detail;
      let msg = t("frontend.subscriptions.error_reminder_settings");
      if (typeof detail === "string") {
        msg = detail;
      } else if (Array.isArray(detail) && detail.length > 0) {
        msg = detail.map((d) => d.msg || "Unknown error").join("; ");
      } else if (err instanceof Error) {
        msg = err.message;
      }
      setError(msg);
    } finally {
      setIsLoading(false);
    }
  }, [open]);

  useEffect(() => {
    loadData();
  }, [loadData]);

  // ── Validation ──────────────────────────────────────────────
  const validate = useCallback(() => {
    const errors: Record<string, string> = {};

    if (settings.reminders_enabled) {
      if (!settings.timezone) {
        errors.timezone = t("frontend.subscriptions.error_timezone_required");
      }
      if (settings.warning_days.length === 0) {
        errors.warning_days = t("frontend.subscriptions.error_warning_days_required");
      }
      if (
        !/^\d{2}:\d{2}$/.test(settings.reminder_time) ||
        !/^([01]\d|2[0-3]):[0-5]\d$/.test(settings.reminder_time)
      ) {
        errors.reminder_time = t("frontend.subscriptions.error_invalid_time");
      }
    }

    setValidationErrors(errors);
    return Object.keys(errors).length === 0;
  }, [settings]);

  useEffect(() => {
    if (open) validate();
  }, [settings, open, validate]);

  // ── Warning day toggles ─────────────────────────────────────
  function toggleWarningDay(day: number) {
    setSettings((prev) => {
      const days = prev.warning_days.includes(day)
        ? prev.warning_days.filter((d) => d !== day)
        : [...prev.warning_days, day].sort((a, b) => a - b);
      return { ...prev, warning_days: days };
    });
  }

  function addCustomDay() {
    const day = parseInt(customDay, 10);
    if (!isNaN(day) && day > 0 && !settings.warning_days.includes(day)) {
      setSettings((prev) => ({
        ...prev,
        warning_days: [...prev.warning_days, day].sort((a, b) => a - b),
      }));
      setCustomDay("");
    }
  }

  function removeWarningDay(day: number) {
    setSettings((prev) => ({
      ...prev,
      warning_days: prev.warning_days.filter((d) => d !== day),
    }));
  }

  // ── Save ────────────────────────────────────────────────────
  async function handleSave() {
    if (!validate()) return;

    setIsSaving(true);
    setError("");

    try {
      await updateReminderSettings(settings);
      toast.success(t("frontend.subscriptions.reminder_saved"));
      onOpenChange(false);
    } catch (err: unknown) {
      const apiErr = err as {
        response?: { data?: { detail?: string | Array<{ msg?: string }> } }
      };
      const detail = apiErr.response?.data?.detail;
      let msg = t("frontend.subscriptions.error_reminder_settings");
      if (typeof detail === "string") {
        msg = detail;
      } else if (Array.isArray(detail) && detail.length > 0) {
        msg = detail.map((d) => d.msg || "Unknown error").join("; ");
      } else if (err instanceof Error) {
        msg = err.message;
      }
      setError(msg);
    } finally {
      setIsSaving(false);
    }
  }

  // ── Timezone groups ─────────────────────────────────────────
  const timezoneGroups = groupTimezones(timezones);
  const hasTimezoneError = !!(validationErrors.timezone && settings.reminders_enabled);
  const hasWarningDaysError = !!(validationErrors.warning_days && settings.reminders_enabled);
  const hasTimeError = !!(validationErrors.reminder_time && settings.reminders_enabled);

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-[780px] sm:max-w-[780px] w-[95vw] max-h-[85vh] flex flex-col p-0 gap-0 overflow-hidden">
        <DialogHeader className="px-8 pt-6 pb-4 border-b">
          <DialogTitle className="text-lg">{t("frontend.subscriptions.reminder_settings_title")}</DialogTitle>
        </DialogHeader>

        <div className="flex-1 overflow-y-auto px-8 py-6">
          {isLoading ? (
            <div className="space-y-5">
              <Skeleton className="h-12 w-full" />
              <Skeleton className="h-12 w-full" />
              <Skeleton className="h-24 w-full" />
              <Skeleton className="h-12 w-full" />
            </div>
          ) : (
            <div className="space-y-7">
              {error && (
                <Alert variant="destructive">
                  <AlertCircle className="h-4 w-4" />
                  <span>{error}</span>
                </Alert>
              )}

              {/* ── Enable toggle ────────────────────────────── */}
              <div className="flex items-center justify-between">
                <div className="space-y-1">
                  <Label className="text-base font-medium">{t("frontend.subscriptions.reminders_enabled")}</Label>
                  <p className="text-sm text-muted-foreground">
                    {t("frontend.subscriptions.reminders_desc")}
                  </p>
                </div>
                <Switch
                  checked={settings.reminders_enabled}
                  onCheckedChange={(checked) =>
                    setSettings((prev) => ({
                      ...prev,
                      reminders_enabled: checked,
                    }))
                  }
                />
              </div>

              {settings.reminders_enabled && (
                <>
                  <Separator />

                  {/* ── Timezone ──────────────────────────────── */}
                  <div className="space-y-2.5">
                    <Label
                      className={`text-sm font-medium ${hasTimezoneError ? "text-destructive" : ""}`}
                    >
                      {t("frontend.subscriptions.timezone")}
                    </Label>
                    <Select
                      value={settings.timezone}
                      onValueChange={(value) =>
                        setSettings((prev) => ({
                          ...prev,
                          timezone: value ?? "",
                        }))
                      }
                    >
                      <SelectTrigger
                        className={`w-full ${hasTimezoneError ? "border-destructive" : ""}`}
                      >
                        <SelectValue placeholder={t("frontend.subscriptions.timezone")} />
                      </SelectTrigger>
                      <SelectContent>
                        {Object.entries(timezoneGroups).map(
                          ([group, tzs]) => (
                            <SelectGroup key={group}>
                              <SelectLabel>{group}</SelectLabel>
                              {tzs.map((tz) => (
                                <SelectItem key={tz.value} value={tz.value}>
                                  {tz.label}
                                </SelectItem>
                              ))}
                            </SelectGroup>
                          )
                        )}
                      </SelectContent>
                    </Select>
                    {settings.timezone === "UTC" && (
                      <p className="text-xs text-amber-600 dark:text-amber-400">
                        ⚠️ Reminders will be sent in UTC. Consider selecting
                        your local timezone.
                      </p>
                    )}
                    {hasTimezoneError && (
                      <p className="text-xs text-destructive">
                        {validationErrors.timezone}
                      </p>
                    )}
                  </div>

                  {/* ── Warning days ──────────────────────────── */}
                  <div className="space-y-2.5">
                    <Label
                      className={`text-sm font-medium ${hasWarningDaysError ? "text-destructive" : ""}`}
                    >
                      {t("frontend.subscriptions.warning_days")}
                    </Label>

                    <div className="flex flex-wrap items-center gap-2">
                      {[7, 3, 1].map((day) => (
                        <label
                          key={day}
                          className="flex items-center gap-2 px-3 py-2 rounded-md border cursor-pointer hover:bg-accent transition-colors"
                        >
                          <input
                            type="checkbox"
                            checked={settings.warning_days.includes(day)}
                            onChange={() => toggleWarningDay(day)}
                            className="rounded"
                          />
                          <span className="text-sm">
                            {day} {day === 1 ? "day" : "days"}
                          </span>
                        </label>
                      ))}

                      <div className="flex items-center gap-1.5">
                        <Input
                          type="number"
                          min={1}
                          value={customDay}
                          onChange={(e) => setCustomDay(e.target.value)}
                          placeholder="Custom"
                          className="w-20 h-9 text-sm"
                          onKeyDown={(e) => {
                            if (e.key === "Enter") {
                              e.preventDefault();
                              addCustomDay();
                            }
                          }}
                        />
                        <Button
                          type="button"
                          variant="outline"
                          size="icon"
                          className="h-9 w-9 shrink-0"
                          onClick={addCustomDay}
                          disabled={!customDay}
                        >
                          <Plus className="h-4 w-4" />
                        </Button>
                      </div>
                    </div>

                    {settings.warning_days.length > 0 && (
                      <div className="flex flex-wrap gap-2 mt-3">
                        {settings.warning_days.map((day) => (
                          <span
                            key={day}
                            className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-full bg-primary/10 text-primary text-sm font-medium"
                          >
                            {day} {day === 1 ? "day" : "days"}
                            <button
                              type="button"
                              onClick={() => removeWarningDay(day)}
                              className="hover:text-destructive transition-colors"
                            >
                              <X className="h-3.5 w-3.5" />
                            </button>
                          </span>
                        ))}
                      </div>
                    )}

                    {hasWarningDaysError && (
                      <p className="text-xs text-destructive">
                        {validationErrors.warning_days}
                      </p>
                    )}
                  </div>

                  {/* ── Reminder time ─────────────────────────── */}
                  <div className="space-y-2.5">
                    <Label
                      className={`text-sm font-medium ${hasTimeError ? "text-destructive" : ""}`}
                    >
                      {t("frontend.subscriptions.reminder_time")}
                    </Label>
                    <p className="text-sm text-muted-foreground">
                      {t("frontend.subscriptions.reminder_time_help")}
                    </p>
                    <Input
                      type="time"
                      value={settings.reminder_time}
                      onChange={(e) =>
                        setSettings((prev) => ({
                          ...prev,
                          reminder_time: e.target.value,
                        }))
                      }
                      className={
                        hasTimeError ? "border-destructive w-40" : "w-40"
                      }
                    />
                    {hasTimeError && (
                      <p className="text-xs text-destructive">
                        {validationErrors.reminder_time}
                      </p>
                    )}
                  </div>

                  {/* ── Recipient mode ────────────────────────── */}
                  <div className="space-y-2.5">
                    <Label className="text-sm font-medium">{t("frontend.subscriptions.recipients")}</Label>
                    <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
                      {[
                        {
                          value: "tenant_only",
                          label: t("frontend.subscriptions.recipient_mode_tenant_only"),
                          desc: "Admin only",
                        },
                        {
                          value: "client_only",
                          label: t("frontend.subscriptions.recipient_mode_client_only"),
                          desc: "Client only",
                        },
                        {
                          value: "both",
                          label: t("frontend.subscriptions.recipient_mode_both"),
                          desc: "Both",
                        },
                      ].map((opt) => (
                        <label
                          key={opt.value}
                          className={`flex flex-col items-center gap-1.5 p-3 rounded-lg border cursor-pointer transition-colors ${
                            settings.recipient_mode === opt.value
                              ? "border-primary bg-primary/5"
                              : "border-border hover:bg-accent"
                          }`}
                        >
                          <input
                            type="radio"
                            name="recipient_mode"
                            value={opt.value}
                            checked={settings.recipient_mode === opt.value}
                            onChange={(e) =>
                              setSettings((prev) => ({
                                ...prev,
                                recipient_mode: e.target.value as
                                  | "tenant_only"
                                  | "client_only"
                                  | "both",
                              }))
                            }
                            className="sr-only"
                          />
                          <span className="text-sm font-medium">{opt.desc}</span>
                          <span className="text-xs text-muted-foreground text-center">{opt.label}</span>
                        </label>
                      ))}
                    </div>
                  </div>

                  <Separator />

                  {/* ── Custom messages ───────────────────────── */}
                  <div className="space-y-4">
                    <div>
                      <Label className="text-sm font-medium">
                        Custom messages
                      </Label>
                      <p className="text-sm text-muted-foreground mt-1">
                        Use{" "}
                        <code className="px-1.5 py-0.5 rounded bg-muted text-xs">
                          {"{{placeholder}}"}
                        </code>{" "}
                        for dynamic values: client_name, service_name, days, streaming_email, expires_at
                      </p>
                    </div>

                    <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                      {/* Tenant message */}
                      <div className="space-y-2">
                        <Label className="text-sm">
                          Message to admin
                        </Label>
                        <textarea
                          value={
                            settings.custom_message_tenant ||
                            DEFAULT_TENANT_MESSAGE
                          }
                          onChange={(e) =>
                            setSettings((prev) => ({
                              ...prev,
                              custom_message_tenant: e.target.value,
                            }))
                          }
                          rows={4}
                          className="w-full rounded-md border border-input bg-transparent px-3 py-2 text-sm placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring resize-none"
                        />
                      </div>

                      {/* Client message */}
                      <div className="space-y-2">
                        <Label className="text-sm">
                          Message to client
                        </Label>
                        <textarea
                          value={
                            settings.custom_message_client ||
                            DEFAULT_CLIENT_MESSAGE
                          }
                          onChange={(e) =>
                            setSettings((prev) => ({
                              ...prev,
                              custom_message_client: e.target.value,
                            }))
                          }
                          rows={4}
                          className="w-full rounded-md border border-input bg-transparent px-3 py-2 text-sm placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring resize-none"
                        />
                      </div>
                    </div>

                    {/* Live preview */}
                    <div className="space-y-2">
                      <Label className="text-sm text-muted-foreground">
                        Preview
                      </Label>
                      <div className="rounded-lg bg-muted/50 p-4 text-sm leading-relaxed">
                        {renderPreview(
                          settings.custom_message_tenant ||
                            DEFAULT_TENANT_MESSAGE
                        )}
                      </div>
                    </div>
                  </div>
                </>
              )}
            </div>
          )}
        </div>

        <DialogFooter className="px-8 py-4 border-t bg-muted/30">
          <Button
            variant="outline"
            onClick={() => onOpenChange(false)}
            disabled={isSaving}
          >
            {t("frontend.common.cancel")}
          </Button>
          <Button
            onClick={handleSave}
            disabled={isSaving || isLoading || Object.keys(validationErrors).length > 0}
          >
            {isSaving ? t("frontend.common.save") : t("frontend.common.save")}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
