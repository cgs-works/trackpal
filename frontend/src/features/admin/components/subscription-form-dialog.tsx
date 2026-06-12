import { useState, useEffect } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
} from "@/components/ui/select";
import { t } from "@/i18n";
import {
  type Subscription,
  type Client,
  type Service,
  type Plan,
  type SubscriptionCreate,
} from "../services/subscription-api";

function getDefaultStartsAt(): string {
  const now = new Date();
  return now.toISOString().slice(0, 16);
}

function getDefaultExpiresAt(startsAt: string, durationType: string): string {
  const start = new Date(startsAt);
  switch (durationType) {
    case "1_month":
      start.setMonth(start.getMonth() + 1);
      break;
    case "3_months":
      start.setMonth(start.getMonth() + 3);
      break;
    case "6_months":
      start.setMonth(start.getMonth() + 6);
      break;
    case "9_months":
      start.setMonth(start.getMonth() + 9);
      break;
    case "1_year":
      start.setFullYear(start.getFullYear() + 1);
      break;
    default:
      return "";
  }
  return start.toISOString().slice(0, 16);
}

interface SubscriptionFormDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  mode: "create" | "edit";
  subscription?: Subscription | null;
  clients: Client[];
  services: Service[];
  plans: Plan[];
  loadingPlans: boolean;
  onServiceChange: (serviceId: string) => void;
  onSubmit: (payload: SubscriptionCreate) => Promise<void>;
  saving: boolean;
  error: string;
}

export function SubscriptionFormDialog({
  open,
  onOpenChange,
  mode,
  subscription,
  clients,
  services,
  plans,
  loadingPlans,
  onServiceChange,
  onSubmit,
  saving,
  error,
}: SubscriptionFormDialogProps) {
  const DURATION_OPTIONS = [
    { value: "1_month", label: t("frontend.subscriptions.duration_1_month") },
    { value: "3_months", label: t("frontend.subscriptions.duration_3_months") },
    { value: "6_months", label: t("frontend.subscriptions.duration_6_months") },
    { value: "9_months", label: t("frontend.subscriptions.duration_9_months") },
    { value: "1_year", label: t("frontend.subscriptions.duration_1_year") },
    { value: "custom", label: t("frontend.subscriptions.duration_custom") },
  ];

  const isEdit = mode === "edit";

  const [clientId, setClientId] = useState("");
  const [serviceId, setServiceId] = useState("");
  const [planId, setPlanId] = useState("");
  const [streamingEmail, setStreamingEmail] = useState("");
  const [streamingPassword, setStreamingPassword] = useState("");
  const [profileName, setProfileName] = useState("");
  const [profilePin, setProfilePin] = useState("");
  const [durationType, setDurationType] = useState("1_month");
  const [startsAt, setStartsAt] = useState(getDefaultStartsAt());
  const [expiresAt, setExpiresAt] = useState("");

  // Auto-calculate expires_at when duration or starts_at changes
  useEffect(() => {
    if (durationType !== "custom") {
      setExpiresAt(getDefaultExpiresAt(startsAt, durationType));
    }
  }, [durationType, startsAt]);

  // Populate form for edit mode
  useEffect(() => {
    if (open && isEdit && subscription) {
      setClientId(subscription.client_id);
      setServiceId(subscription.service_id);
      setPlanId(subscription.plan_id);
      setStreamingEmail(subscription.streaming_email);
      setStreamingPassword("");
      setProfileName(subscription.profile_name || "");
      setProfilePin("");
      setDurationType(subscription.duration_type);
      setStartsAt(subscription.starts_at.slice(0, 16));
      setExpiresAt(subscription.expires_at.slice(0, 16));
    } else if (open && !isEdit) {
      setClientId("");
      setServiceId("");
      setPlanId("");
      setStreamingEmail("");
      setStreamingPassword("");
      setProfileName("");
      setProfilePin("");
      setDurationType("1_month");
      setStartsAt(getDefaultStartsAt());
      setExpiresAt(getDefaultExpiresAt(getDefaultStartsAt(), "1_month"));
    }
  }, [open, isEdit, subscription]);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    const payload: SubscriptionCreate = {
      client_id: clientId,
      service_id: serviceId,
      plan_id: planId,
      streaming_email: streamingEmail,
      duration_type: durationType,
      starts_at: startsAt,
    };
    if (streamingPassword) payload.streaming_password = streamingPassword;
    if (profileName) payload.profile_name = profileName;
    if (profilePin) payload.profile_pin = profilePin;
    if (durationType === "custom" && expiresAt) {
      payload.expires_at = expiresAt;
    } else if (expiresAt) {
      payload.expires_at = expiresAt;
    }
    await onSubmit(payload);
  }

  const title = isEdit ? t("frontend.subscriptions.edit_title") : t("frontend.subscriptions.new_title");
  const hasProfile = profileName.trim().length > 0;

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-lg max-h-[90vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle>{title}</DialogTitle>
          <DialogDescription>
            {isEdit
              ? "Update subscription details."
              : "Create a new subscription for a client."}
          </DialogDescription>
        </DialogHeader>

        {error && (
          <div className="rounded-lg bg-destructive/10 border border-destructive/20 p-3 text-sm text-destructive">
            {error}
          </div>
        )}

        <form onSubmit={handleSubmit} className="flex flex-col gap-4">
          {/* Client */}
          <div className="flex flex-col gap-2">
            <Label>{t("frontend.subscriptions.client")}</Label>
            <Select value={clientId} onValueChange={(v) => setClientId(v ?? "")} disabled={isEdit}>
              <SelectTrigger>
                {clientId
                  ? clients.find((c) => c.id === clientId)?.full_name
                  : t("frontend.subscriptions.select_client")}
              </SelectTrigger>
              <SelectContent>
                {clients.map((c) => (
                  <SelectItem key={c.id} value={c.id}>
                    {c.full_name}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          {/* Service */}
          <div className="flex flex-col gap-2">
            <Label>{t("frontend.subscriptions.service")}</Label>
            <Select value={serviceId} onValueChange={(v) => { setServiceId(v ?? ""); setPlanId(""); onServiceChange(v ?? ""); }} disabled={isEdit}>
              <SelectTrigger>
                {serviceId
                  ? services.find((s) => s.id === serviceId)?.name
                  : t("frontend.subscriptions.select_service")}
              </SelectTrigger>
              <SelectContent>
                {services.map((s) => (
                  <SelectItem key={s.id} value={s.id}>
                    {s.name}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          {/* Plan */}
          <div className="flex flex-col gap-2">
            <Label>{t("frontend.subscriptions.plan")}</Label>
            <Select value={planId} onValueChange={(v) => setPlanId(v ?? "")} disabled={isEdit || !serviceId || loadingPlans}>
              <SelectTrigger>
                {loadingPlans
                  ? t("frontend.subscriptions.loading")
                  : planId
                    ? plans.find((p) => p.id === planId)?.name
                    : t("frontend.subscriptions.select_plan")}
              </SelectTrigger>
              <SelectContent>
                {plans.map((p) => (
                  <SelectItem key={p.id} value={p.id}>
                    {p.name}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          {/* Streaming Email */}
          <div className="flex flex-col gap-2">
            <Label htmlFor="streaming_email">{t("frontend.subscriptions.email")}</Label>
            <Input
              id="streaming_email"
              type="email"
              required
              value={streamingEmail}
              onChange={(e) => setStreamingEmail(e.target.value)}
            />
          </div>

          {/* Password */}
          <div className="flex flex-col gap-2">
            <Label htmlFor="streaming_password">
              {t("frontend.subscriptions.streaming_password")}
              {isEdit && subscription?.has_password && (
                <span className="text-muted-foreground text-xs ml-2">
                  (leave blank to keep current)
                </span>
              )}
            </Label>
            <Input
              id="streaming_password"
              type="password"
              autoComplete="new-password"
              value={streamingPassword}
              onChange={(e) => setStreamingPassword(e.target.value)}
              placeholder={isEdit ? "••••••••" : ""}
            />
          </div>

          {/* Profile Name */}
          <div className="flex flex-col gap-2">
            <Label htmlFor="profile_name">{t("frontend.subscriptions.profile_name")} {t("frontend.subscriptions.optional")}</Label>
            <Input
              id="profile_name"
              value={profileName}
              onChange={(e) => setProfileName(e.target.value)}
            />
          </div>

          {/* Profile PIN */}
          <div className="flex flex-col gap-2">
            <Label htmlFor="profile_pin">
              {t("frontend.subscriptions.pin")}
              {isEdit && subscription?.has_pin && (
                <span className="text-muted-foreground text-xs ml-2">
                  (leave blank to keep current)
                </span>
              )}
            </Label>
            <Input
              id="profile_pin"
              type="password"
              value={profilePin}
              onChange={(e) => setProfilePin(e.target.value)}
              disabled={!hasProfile}
              placeholder={hasProfile ? "" : "Enter profile name first"}
            />
          </div>

          {/* Duration */}
          <div className="flex flex-col gap-2">
            <Label>{t("frontend.subscriptions.duration")}</Label>
            <Select value={durationType} onValueChange={(v) => setDurationType(v ?? "")}>
              <SelectTrigger>
                {DURATION_OPTIONS.find((o) => o.value === durationType)?.label || durationType}
              </SelectTrigger>
              <SelectContent>
                {DURATION_OPTIONS.map((opt) => (
                  <SelectItem key={opt.value} value={opt.value}>
                    {opt.label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          {/* Dates */}
          <div className="grid grid-cols-2 gap-3">
            <div className="flex flex-col gap-2">
              <Label htmlFor="starts_at">{t("frontend.subscriptions.start_date")}</Label>
              <Input
                id="starts_at"
                type="datetime-local"
                required
                value={startsAt}
                onChange={(e) => setStartsAt(e.target.value)}
              />
            </div>
            <div className="flex flex-col gap-2">
              <Label htmlFor="expires_at">{t("frontend.subscriptions.end_date")}</Label>
              <Input
                id="expires_at"
                type="datetime-local"
                required={durationType === "custom"}
                value={expiresAt}
                onChange={(e) => setExpiresAt(e.target.value)}
                readOnly={durationType !== "custom"}
              />
            </div>
          </div>

          <DialogFooter>
            <Button
              type="button"
              variant="outline"
              onClick={() => onOpenChange(false)}
              disabled={saving}
            >
              {t("frontend.common.cancel")}
            </Button>
            <Button
              type="submit"
              disabled={saving || !clientId || !serviceId || !planId}
            >
              {saving ? t("frontend.subscriptions.saving") : t("frontend.subscriptions.save")}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
