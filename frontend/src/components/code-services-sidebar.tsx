import { useState } from "react"
import {
  Sheet,
  SheetContent,
  SheetHeader,
  SheetTitle,
  SheetDescription,
} from "@/components/ui/sheet"
import { Switch } from "@/components/ui/switch"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { Save } from "lucide-react"

interface Service {
  service_key: string
  label: string
  is_active: boolean
}

interface CodeServicesSidebarProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  services: Service[]
  loading: boolean
  onSave: (services: Service[]) => Promise<void>
}

export function CodeServicesSidebar({
  open,
  onOpenChange,
  services: initialServices,
  loading,
  onSave,
}: CodeServicesSidebarProps) {
  const [services, setServices] = useState<Service[]>(initialServices)
  const [saving, setSaving] = useState(false)

  // Sync with props when they change
  if (
    initialServices.length > 0 &&
    JSON.stringify(initialServices) !== JSON.stringify(services)
  ) {
    setServices(initialServices)
  }

  function toggleService(key: string) {
    setServices((prev) =>
      prev.map((svc) =>
        svc.service_key === key ? { ...svc, is_active: !svc.is_active } : svc
      )
    )
  }

  async function handleSave() {
    setSaving(true)
    try {
      await onSave(services)
    } finally {
      setSaving(false)
    }
  }

  const activeCount = services.filter((s) => s.is_active).length

  return (
    <Sheet open={open} onOpenChange={onOpenChange}>
      <SheetContent side="right" className="w-[320px] sm:w-[380px]">
        <SheetHeader>
          <SheetTitle>Code Services</SheetTitle>
          <SheetDescription>
            Configure which services are enabled for this tenant.
          </SheetDescription>
        </SheetHeader>

        <div className="flex-1 overflow-y-auto px-4">
          {loading ? (
            <div className="space-y-3">
              {[1, 2, 3].map((i) => (
                <div key={i} className="h-16 rounded-lg bg-muted animate-pulse" />
              ))}
            </div>
          ) : services.length === 0 ? (
            <p className="text-sm text-muted-foreground text-center py-8">
              No code services available.
            </p>
          ) : (
            <div className="space-y-1">
              {services.map((svc) => (
                <div
                  key={svc.service_key}
                  className="flex items-center justify-between gap-3 rounded-lg p-3 hover:bg-muted/50 transition-colors"
                >
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2">
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

        <div className="border-t p-4">
          <div className="flex items-center justify-between mb-3">
            <span className="text-sm text-muted-foreground">
              {activeCount} of {services.length} active
            </span>
          </div>
          <Button
            onClick={handleSave}
            disabled={saving}
            className="w-full"
          >
            <Save className="h-4 w-4 mr-2" />
            {saving ? "Saving..." : "Save Changes"}
          </Button>
        </div>
      </SheetContent>
    </Sheet>
  )
}
