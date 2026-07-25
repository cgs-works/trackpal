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
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>{t("frontend.master.demos.create_title")}</DialogTitle>
          <DialogDescription>
            {t("frontend.master.demos.create_description")}
          </DialogDescription>
        </DialogHeader>

        {error && (
          <div
            role="alert"
            className="rounded-lg border border-destructive/20 bg-destructive/10 p-3 text-sm text-destructive"
          >
            {error}
          </div>
        )}

        <form onSubmit={onSubmit} className="flex flex-col gap-4">
          <div className="flex flex-col gap-2">
            <Label htmlFor="demo-name">{t("frontend.master.demos.name_label")}</Label>
            <Input
              id="demo-name"
              value={form.name}
              onChange={(event) => onFormChange("name", event.target.value)}
              required
              autoFocus
            />
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
              <SelectTrigger id="demo-plan">
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
