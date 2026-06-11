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
  type ReminderSettings,
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
    } catch (err) {
      setError(
        err instanceof Error ? err.message : t("frontend.subscriptions.error_reminder_settings")
      );
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
    } catch (err) {
      setError(
        err instanceof Error ? err.message : t("frontend.subscriptions.error_reminder_settings")
      );
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
      <DialogContent className="max-w-[560px] max-h-[90vh] overflow-y-auto p-0">
        <DialogHeader className="p-6 pb-0">
          <DialogTitle>{t("frontend.subscriptions.reminder_settings_title")}</DialogTitle>
        </DialogHeader>

        <div className="p-6 space-y-6">
          {isLoading ? (
            <div className="space-y-4">
              <Skeleton className="h-10 w-full" />
              <Skeleton className="h-10 w-full" />
              <Skeleton className="h-20 w-full" />
              <Skeleton className="h-10 w-full" />
            </div>
          ) : (
            <>
              {error && (
                <Alert variant="destructive">
                  <AlertCircle className="h-4 w-4" />
                  <span>{error}</span>
                </Alert>
              )}

              {/* ── Enable toggle ────────────────────────────── */}
              <div className="flex items-center justify-between">
                <div className="space-y-0.5">
                  <Label className="text-base">{t("frontend.subscriptions.reminders_enabled")}</Label>
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
                  <div className="space-y-2">
                    <Label
                      className={hasTimezoneError ? "text-destructive" : ""}
                    >
                      {t("frontend.subscriptions.timezone")}
                    </Label>
                    <Select
                      value={settings.timezone}
                      onValueChange={(value) =>
                        setSettings((prev) => ({
                          ...prev,
                          timezone: value,
                        }))
                      }
                    >
                      <SelectTrigger
                        className={
                          hasTimezoneError ? "border-destructive" : ""
                        }
                      >
                        <SelectValue placeholder={t("frontend.subscriptions.timezone")} />
                      </SelectTrigger>
                      <SelectContent>
                        {Object.entries(timezoneGroups).map(
                          ([group, tzs]) => (
                            <SelectItem key={`group-${group}`} value={group} disabled>
                              <span className="font-semibold text-muted-foreground">
                                {group}
                              </span>
                            </SelectItem>
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
                  <div className="space-y-2">
                    <Label
                      className={hasWarningDaysError ? "text-destructive" : ""}
                    >
                      {t("frontend.subscriptions.warning_days")}
                    </Label>
                    <p className="text-sm text-muted-foreground">
                      {t("frontend.subscriptions.reminders_desc")}
                    </p>

                    <div className="flex flex-wrap gap-2">
                      {[7, 3, 1].map((day) => (
                        <label
                          key={day}
                          className="flex items-center gap-2 px-3 py-1.5 rounded-md border cursor-pointer hover:bg-accent"
                        >
                          <input
                            type="checkbox"
                            checked={settings.warning_days.includes(day)}
                            onChange={() => toggleWarningDay(day)}
                            className="rounded"
                          />
                          <span className="text-sm">
                            {day} {day === 1 ? t("frontend.subscriptions.day") : t("frontend.subscriptions.day")}
                          </span>
                        </label>
                      ))}

                      <div className="flex items-center gap-1">
                        <Input
                          type="number"
                          min={1}
                          value={customDay}
                          onChange={(e) => setCustomDay(e.target.value)}
                          placeholder={t("frontend.subscriptions.duration_custom")}
                          className="w-20 h-8 text-sm"
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
                          className="h-8 w-8 shrink-0"
                          onClick={addCustomDay}
                          disabled={!customDay}
                        >
                          <Plus className="h-3 w-3" />
                        </Button>
                      </div>
                    </div>

                    {settings.warning_days.length > 0 && (
                      <div className="flex flex-wrap gap-1.5 mt-2">
                        {settings.warning_days.map((day) => (
                          <span
                            key={day}
                            className="inline-flex items-center gap-1 px-2.5 py-1 rounded-full bg-primary/10 text-primary text-xs font-medium"
                          >
                            {day} {day === 1 ? t("frontend.subscriptions.day") : t("frontend.subscriptions.day")}
                            <button
                              type="button"
                              onClick={() => removeWarningDay(day)}
                              className="hover:text-destructive"
                            >
                              <X className="h-3 w-3" />
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
                  <div className="space-y-2">
                    <Label
                      className={hasTimeError ? "text-destructive" : ""}
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
                        hasTimeError ? "border-destructive" : "w-32"
                      }
                    />
                    {hasTimeError && (
                      <p className="text-xs text-destructive">
                        {validationErrors.reminder_time}
                      </p>
                    )}
                  </div>

                  {/* ── Recipient mode ────────────────────────── */}
                  <div className="space-y-2">
                    <Label>{t("frontend.subscriptions.recipients")}</Label>
                    <p className="text-sm text-muted-foreground">
                      {t("frontend.subscriptions.reminders_desc")}
                    </p>
                    <div className="space-y-2">
                      {[
                        {
                          value: "tenant_only",
                          label: t("frontend.subscriptions.recipient_mode_tenant_only"),
                          desc: "Only you (the business owner) receives reminders",
                        },
                        {
                          value: "client_only",
                          label: t("frontend.subscriptions.recipient_mode_client_only"),
                          desc: "Only the client receives reminders",
                        },
                        {
                          value: "both",
                          label: t("frontend.subscriptions.recipient_mode_both"),
                          desc: "Both tenant and client receive reminders",
                        },
                      ].map((opt) => (
                        <label
                          key={opt.value}
                          className="flex items-start gap-3 p-3 rounded-md border cursor-pointer hover:bg-accent"
                        >
                          <input
                            type="radio"
                            name="recipient_mode"
                            value={opt.value}
                            checked={
                              settings.recipient_mode === opt.value
                            }
                            onChange={(e) =>
                              setSettings((prev) => ({
                                ...prev,
                                recipient_mode: e.target.value as
                                  | "tenant_only"
                                  | "client_only"
                                  | "both",
                              }))
                            }
                            className="mt-0.5"
                          />
                          <div>
                            <span className="text-sm font-medium">
                              {opt.label}
                            </span>
                            <p className="text-xs text-muted-foreground">
                              {opt.desc}
                            </p>
                          </div>
                        </label>
                      ))}
                    </div>
                  </div>

                  <Separator />

                  {/* ── Custom messages ───────────────────────── */}
                  <div className="space-y-4">
                    <div>
                      <Label className="text-base">
                        Custom messages
                      </Label>
                      <p className="text-sm text-muted-foreground">
                        Write your own reminder message. Use{" "}
                        <code className="px-1 py-0.5 rounded bg-muted text-xs">
                          {"{{placeholder}}"}
                        </code>{" "}
                        for dynamic values.
                      </p>
                    </div>

                    {/* Tenant message */}
                    <div className="space-y-2">
                      <Label className="text-sm">
                        Message to tenant (you)
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
                        rows={3}
                        className="w-full rounded-md border border-input bg-transparent px-3 py-2 text-sm ring-offset-background placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 resize-none"
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
                        rows={3}
                        className="w-full rounded-md border border-input bg-transparent px-3 py-2 text-sm ring-offset-background placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 resize-none"
                      />
                    </div>

                    {/* Placeholders reference */}
                    <div className="text-xs text-muted-foreground">
                      <span className="font-medium">Available:</span>{" "}
                      {"{{client_name}}"}, {"{{service_name}}"},{" "}
                      {"{{days}}"}, {"{{streaming_email}}"},{" "}
                      {"{{expires_at}}"}
                    </div>

                    {/* Live preview */}
                    <div className="space-y-2">
                      <Label className="text-sm text-muted-foreground">
                        Preview
                      </Label>
                      <div className="rounded-md bg-muted p-3 text-sm">
                        {renderPreview(
                          settings.custom_message_tenant ||
                            DEFAULT_TENANT_MESSAGE
                        )}
                      </div>
                    </div>
                  </div>
                </>
              )}
            </>
          )}
        </div>

        <DialogFooter className="p-6 pt-0">
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
