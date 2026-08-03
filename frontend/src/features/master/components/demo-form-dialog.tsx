import type { FormEvent } from "react";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
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
import { t } from "@/i18n";
import type { TenantPlan } from "@/features/auth/services/auth-api";

export interface DemoForm {
  name: string;
  plan: TenantPlan;
  locale: "en" | "es";
}

interface DemoFormDialogProps {
  open: boolean;
  form: DemoForm;
  saving: boolean;
  error: string;
  onOpenChange: (open: boolean) => void;
  onFormChange: (key: keyof DemoForm, value: string) => void;
  onSubmit: (event: FormEvent) => void;
}

export function DemoFormDialog({
  open,
  form,
  saving,
  error,
  onOpenChange,
  onFormChange,
  onSubmit,
}: DemoFormDialogProps) {
  return (
    <Dialog open={open} onOpenChange={(nextOpen) => { if (!saving) onOpenChange(nextOpen); }}>
      <DialogContent className="max-h-[min(90dvh,36rem)] overflow-y-auto sm:max-w-md">
        <DialogHeader>
          <DialogTitle>{t("frontend.master.demos.create_title")}</DialogTitle>
          <DialogDescription>
            {t("frontend.master.demos.create_description")}
          </DialogDescription>
        </DialogHeader>

        {error && (
          <div
            id="demo-form-error"
            role="alert"
            className="rounded-lg border border-destructive/20 bg-destructive/10 p-3 text-sm text-destructive"
          >
            {error}
          </div>
        )}

        <form onSubmit={onSubmit} className="flex flex-col gap-4" aria-busy={saving}>
          <div className="flex flex-col gap-2">
            <Label htmlFor="demo-name">{t("frontend.master.demos.name_label")}</Label>
            <Input
              id="demo-name"
              value={form.name}
              onChange={(event) => onFormChange("name", event.target.value)}
              required
              maxLength={120}
              autoComplete="organization"
              autoFocus
              disabled={saving}
              aria-invalid={Boolean(error)}
              aria-describedby={error ? "demo-form-error" : undefined}
            />
          </div>

          <div className="flex flex-col gap-2">
            <Label htmlFor="demo-locale">{t("frontend.master.demos.locale_label")}</Label>
            <Select
              value={form.locale}
              onValueChange={(value) => {
                if (value === "en" || value === "es") {
                  onFormChange("locale", value);
                }
              }}
            >
              <SelectTrigger id="demo-locale" disabled={saving}>
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="en">{t("frontend.master.demos.locale_en")}</SelectItem>
                <SelectItem value="es">{t("frontend.master.demos.locale_es")}</SelectItem>
              </SelectContent>
            </Select>
          </div>

          <div className="flex flex-col gap-2">
            <Label htmlFor="demo-plan">{t("frontend.master.demos.plan_label")}</Label>
            <Select
              value={form.plan}
              onValueChange={(value) => {
                if (value === "starter" || value === "pro") {
                  onFormChange("plan", value);
                }
              }}
            >
              <SelectTrigger id="demo-plan" disabled={saving} aria-describedby={error ? "demo-form-error" : undefined}>
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="starter">{t("frontend.master.demos.starter")}</SelectItem>
                <SelectItem value="pro">{t("frontend.master.demos.pro")}</SelectItem>
              </SelectContent>
            </Select>
          </div>

          <DialogFooter>
            <Button
              type="button"
              variant="outline"
              onClick={() => onOpenChange(false)}
              disabled={saving}
            >
              {t("frontend.master.demos.cancel")}
            </Button>
            <Button type="submit" disabled={saving}>
              {saving
                ? t("frontend.master.demos.creating")
                : t("frontend.master.demos.submit_create")}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
