import { useCallback, useEffect, useState } from "react";
import { toast } from "sonner";
import { Save } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Skeleton } from "@/components/ui/skeleton";
import { Switch } from "@/components/ui/switch";
import {
  fetchCodeServices,
  saveCodeServices,
  type CodeService,
} from "../services/tenant-api";

interface CodeServicesDialogProps {
  open: boolean
  onOpenChange: (open: boolean) => void
}

export function CodeServicesDialog({
  open,
  onOpenChange,
}: CodeServicesDialogProps) {
  const [services, setServices] = useState<CodeService[]>([]);
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);

  const loadServices = useCallback(async () => {
    setLoading(true);
    try {
      setServices(await fetchCodeServices());
    } catch {
      toast.error("Unable to load code services");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (open) loadServices();
  }, [open, loadServices]);

  function toggleService(key: string) {
    setServices((prev) =>
      prev.map((svc) =>
        svc.service_key === key ? { ...svc, is_active: !svc.is_active } : svc
      )
    );
  }

  async function handleSave() {
    setSaving(true);
    try {
      const payload: Record<string, boolean> = {};
      for (const svc of services) {
        payload[svc.service_key] = svc.is_active;
      }
      await saveCodeServices(payload);
      toast.success("Code services saved");
      onOpenChange(false);
    } catch {
      toast.error("Unable to save code services");
    } finally {
      setSaving(false);
    }
  }

  const activeCount = services.filter((s) => s.is_active).length;

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>Code Services</DialogTitle>
          <DialogDescription>
            Configure which services are enabled globally for all tenants.
          </DialogDescription>
        </DialogHeader>

        <div className="py-4">
          {loading ? (
            <div className="flex flex-col gap-3">
              {[1, 2, 3].map((i) => (
                <Skeleton key={i} className="h-14 w-full rounded-lg" />
              ))}
            </div>
          ) : services.length === 0 ? (
            <p className="text-sm text-muted-foreground text-center py-8">
              No code services available.
            </p>
          ) : (
            <div className="flex flex-col gap-1">
              {services.map((svc) => (
                <div
                  key={svc.service_key}
                  className="flex items-center justify-between gap-3 rounded-lg p-3 hover:bg-muted/50 transition-colors"
                >
                  <div className="flex items-center gap-3">
                    <span className="font-medium text-sm">{svc.label}</span>
                    <Badge
                      variant={svc.is_active ? "default" : "secondary"}
                      className={
                        svc.is_active
                          ? "bg-emerald-100 text-emerald-800 dark:bg-emerald-900 dark:text-emerald-300"
                          : "bg-muted text-muted-foreground"
                      }
                    >
                      {svc.is_active ? "Active" : "Inactive"}
                    </Badge>
                  </div>
                  <Switch
                    checked={svc.is_active}
                    onCheckedChange={() => toggleService(svc.service_key)}
                  />
                </div>
              ))}
            </div>
          )}
        </div>

        <DialogFooter>
          <div className="flex items-center justify-between w-full">
            <span className="text-sm text-muted-foreground">
              {activeCount} of {services.length} active
            </span>
            <Button onClick={handleSave} disabled={saving || loading}>
              <Save className="size-4 mr-2" />
              {saving ? "Saving..." : "Save Changes"}
            </Button>
          </div>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
