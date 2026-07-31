import { useState, useEffect } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { t } from "@/i18n";
import { IconPicker } from "@/features/catalog/components/icon-picker";
import { ServiceIcon } from "@/features/catalog/components/service-icon";
import type { Service, ServiceCreate, ServiceUpdate } from "../services/catalog-api";

export interface ServiceFormDialogProps {
  open: boolean;
  mode: "create" | "edit";
  service?: Service | null;
  saving: boolean;
  error: string;
  onOpenChange(open: boolean): void;
  onSubmit(payload: ServiceCreate | ServiceUpdate): Promise<void>;
}

export function ServiceFormDialog({
  open,
  mode,
  service,
  saving,
  error,
  onOpenChange,
  onSubmit,
}: ServiceFormDialogProps) {
  const [name, setName] = useState("");
  const [icon, setIcon] = useState<string | null>(null);
  const [pickerOpen, setPickerOpen] = useState(false);

  useEffect(() => {
    if (!open) return;
    setName(service?.name ?? "");
    setIcon(service?.icon ?? null);
    setPickerOpen(false);
  }, [open, service]);

  async function handleSubmit() {
    if (!name.trim()) return;
    await onSubmit({ name: name.trim(), icon });
  }

  return (
    <>
      <Dialog open={open} onOpenChange={onOpenChange}>
        <DialogContent className="sm:max-w-sm">
          <DialogHeader>
            <DialogTitle>
              {mode === "create"
                ? t("frontend.catalog.new_service")
                : t("frontend.catalog.edit_service")}
            </DialogTitle>
          </DialogHeader>
          <div className="space-y-4">
            <div className="space-y-2">
              <Label htmlFor="service-name-input">
                {t("frontend.common.name")}
              </Label>
              <Input
                id="service-name-input"
                value={name}
                onChange={(e) => setName(e.target.value)}
                autoFocus
              />
            </div>

            <div className="space-y-2">
              <Label>{t("frontend.catalog.service_icon")}</Label>
              <div className="flex items-center gap-3">
                <ServiceIcon
                  icon={icon}
                  label={name || "service"}
                  className="size-8"
                />
                <Button
                  type="button"
                  variant="outline"
                  size="sm"
                  data-testid="choose-icon-btn"
                  onClick={() => setPickerOpen(true)}
                >
                  {t("frontend.catalog.choose_icon")}
                </Button>
                {icon !== null && (
                  <Button
                    type="button"
                    variant="ghost"
                    size="sm"
                    onClick={() => setIcon(null)}
                  >
                    {t("frontend.catalog.remove_icon")}
                  </Button>
                )}
              </div>
              <p className="text-xs text-muted-foreground">
                {t("frontend.catalog.icon_optional_help")}
              </p>
            </div>

            {error && (
              <p className="text-sm text-destructive">{error}</p>
            )}

            <div className="flex justify-end gap-2">
              <Button
                type="button"
                variant="outline"
                onClick={() => onOpenChange(false)}
                disabled={saving}
              >
                {t("frontend.common.cancel")}
              </Button>
              <Button
                type="button"
                disabled={saving || !name.trim()}
                onClick={handleSubmit}
              >
                {saving
                  ? t("frontend.catalog.saving")
                  : t("frontend.catalog.save_service")}
              </Button>
            </div>
          </div>
        </DialogContent>
      </Dialog>

      <IconPicker
        open={pickerOpen}
        value={icon}
        onOpenChange={setPickerOpen}
        onSelect={setIcon}
      />
    </>
  );
}
