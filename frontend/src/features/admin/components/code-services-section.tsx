import { useState, useEffect, useCallback } from "react";
import { Button } from "@/components/ui/button";
import { Switch } from "@/components/ui/switch";
import { Separator } from "@/components/ui/separator";
import { toast } from "sonner";
import { t } from "@/i18n";
import {
  type TenantCodeService,
  getTenantCodeServices,
  updateTenantCodeServices,
} from "../services/settings-api";

export function CodeServicesSection() {
  const [services, setServices] = useState<TenantCodeService[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");

  const loadServices = useCallback(async () => {
    setIsLoading(true);
    setError("");
    try {
      const data = await getTenantCodeServices();
      setServices(data.services);
    } catch (err) {
      setError(
        err instanceof Error ? err.message : t("frontend.code_services.tenant_error_load")
      );
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    loadServices();
  }, [loadServices]);

  function toggleService(key: string) {
    setServices((prev) =>
      prev.map((s) =>
        s.service_key === key ? { ...s, is_selected: !s.is_selected } : s
      )
    );
  }

  async function handleSave() {
    setSaving(true);
    try {
      const selectedKeys = services
        .filter((s) => s.is_selected)
        .map((s) => s.service_key);
      const data = await updateTenantCodeServices(selectedKeys);
      setServices(data.services);
      toast.success(t("frontend.code_services.tenant_saved"));
    } catch (err) {
      toast.error(
        err instanceof Error ? err.message : t("frontend.code_services.tenant_error_save")
      );
    } finally {
      setSaving(false);
    }
  }

  if (isLoading) {
    return (
      <div className="space-y-3">
        {[1, 2, 3].map((i) => (
          <div key={i} className="h-16 rounded-lg bg-muted animate-pulse" />
        ))}
      </div>
    );
  }

  if (error) {
    return (
      <div className="rounded-lg bg-destructive/10 border border-destructive/20 p-3 text-sm text-destructive">
        {error}
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <p className="text-sm text-muted-foreground">
        {t("frontend.code_services.tenant_description")}
      </p>

      <div className="space-y-1">
        {services.map((service) => {
          const disabled = !service.is_globally_active;
          return (
            <div key={service.service_key}>
              <div className="flex items-center justify-between py-3 px-2 rounded-lg hover:bg-muted/50">
                <div className="flex-1">
                  <p className={`text-sm font-medium ${disabled ? "opacity-50" : ""}`}>
                    {service.label}
                  </p>
                  {disabled && (
                    <p className="text-xs text-muted-foreground">
                      {t("frontend.code_services.tenant_globally_inactive")}
                    </p>
                  )}
                </div>
                <Switch
                  checked={service.is_selected}
                  onCheckedChange={() => toggleService(service.service_key)}
                  disabled={disabled}
                />
              </div>
              <Separator />
            </div>
          );
        })}
      </div>

      <div className="flex justify-end">
        <Button onClick={handleSave} disabled={saving}>
          {saving ? t("frontend.code_services.tenant_saving") : t("frontend.code_services.tenant_save")}
        </Button>
      </div>
    </div>
  );
}
