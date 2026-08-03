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
  SelectValue,
} from "@/components/ui/select";
import type { TenantPlan } from "@/features/auth/services/auth-api";

export interface BusinessForm {
  id: string | null
  full_name: string
  email: string
  phone: string
  client_prefix: string
  username: string
  password: string
  evolution_instance_name: string
  plan: TenantPlan
  locale: "en" | "es"
}

export function getEmptyForm(): BusinessForm {
  return {
    id: null,
    full_name: "",
    email: "",
    phone: "",
    client_prefix: "",
    username: "",
    password: "",
    evolution_instance_name: "",
    plan: "starter",
    locale: "en",
  }
}

interface BusinessFormDialogProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  mode: "create" | "edit"
  form: BusinessForm
  onFormChange: (key: keyof BusinessForm, value: string) => void
  onSubmit: (e: React.FormEvent) => void
  saving: boolean
  error: string
}

export function BusinessFormDialog({
  open,
  onOpenChange,
  mode,
  form,
  onFormChange,
  onSubmit,
  saving,
  error,
}: BusinessFormDialogProps) {
  const isEdit = mode === "edit";
  const title = isEdit ? "Edit Business" : "Create Business";
  const prefixHint = isEdit
    ? "Changing this prefix will update all client login usernames for this business."
    : "Leave blank to auto-generate a unique prefix.";

  return (
    <Dialog open={open} onOpenChange={(o) => { if (!o) onOpenChange(o) }}>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>{title}</DialogTitle>
          <DialogDescription>
            {isEdit
              ? "Update business details and configuration."
              : "Register a new business with an Evolution instance."}
          </DialogDescription>
        </DialogHeader>

        {error && (
          <div className="rounded-lg bg-destructive/10 border border-destructive/20 p-3 text-sm text-destructive">
            {error}
          </div>
        )}

        <form onSubmit={onSubmit} className="flex flex-col gap-4">
          <div className="flex flex-col gap-2">
            <Label htmlFor="full_name">Full Name</Label>
            <Input
              id="full_name"
              required
              value={form.full_name}
              onChange={(e) => onFormChange("full_name", e.target.value)}
            />
          </div>

          {!isEdit && (
            <div className="flex flex-col gap-2">
              <Label htmlFor="tenant_locale">Language</Label>
              <Select value={form.locale} onValueChange={(value) => { if (value === "en" || value === "es") onFormChange("locale", value); }}>
                <SelectTrigger id="tenant_locale">
                  <SelectValue placeholder="Select language" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="en">English</SelectItem>
                  <SelectItem value="es">Spanish</SelectItem>
                </SelectContent>
              </Select>
            </div>
          )}

          <div className="flex flex-col gap-2">
            <Label htmlFor="tenant_plan">Plan</Label>
            <Select value={form.plan} onValueChange={(value) => { if (value) onFormChange("plan", value); }}>
              <SelectTrigger id="tenant_plan">
                <SelectValue placeholder="Select plan" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="starter">Starter</SelectItem>
                <SelectItem value="pro">Pro</SelectItem>
              </SelectContent>
            </Select>
            <p className="text-xs text-muted-foreground">
              Starter enables code lookup only. Pro enables clients, catalog, subscriptions, and reminders.
            </p>
          </div>

          <div className="flex flex-col gap-2">
            <Label htmlFor="email">Email</Label>
            <Input
              id="email"
              type="email"
              required
              value={form.email}
              onChange={(e) => onFormChange("email", e.target.value)}
            />
          </div>

          <div className="flex flex-col gap-2">
            <Label htmlFor="phone">Phone</Label>
            <Input
              id="phone"
              type="tel"
              required
              value={form.phone}
              onChange={(e) => onFormChange("phone", e.target.value)}
            />
          </div>

          <div className="flex flex-col gap-2">
            <Label htmlFor="client_prefix">
              Client Prefix <span className="text-muted-foreground font-normal">(optional)</span>
            </Label>
            <Input
              id="client_prefix"
              maxLength={5}
              value={form.client_prefix}
              onChange={(e) => onFormChange("client_prefix", e.target.value)}
            />
            <p className="text-xs text-muted-foreground">{prefixHint}</p>
          </div>

          {!isEdit && (
            <>
              <div className="flex flex-col gap-2">
                <Label htmlFor="tenant_username">Username</Label>
                <Input
                  id="tenant_username"
                  required
                  value={form.username}
                  onChange={(e) => onFormChange("username", e.target.value)}
                />
              </div>
              <div className="flex flex-col gap-2">
                <Label htmlFor="password">
                  Password <span className="text-muted-foreground font-normal">(optional)</span>
                </Label>
                <Input
                  id="password"
                  type="password"
                  autoComplete="new-password"
                  value={form.password}
                  onChange={(e) => onFormChange("password", e.target.value)}
                />
              </div>
            </>
          )}

          <div className="flex flex-col gap-2">
            <Label htmlFor="evolution_instance_name">Evolution Instance</Label>
            <Input
              id="evolution_instance_name"
              required
              value={form.evolution_instance_name}
              onChange={(e) => onFormChange("evolution_instance_name", e.target.value)}
            />
          </div>

          <DialogFooter>
            <Button type="button" variant="outline" onClick={() => onOpenChange(false)} disabled={saving}>
              Cancel
            </Button>
            <Button type="submit" disabled={saving}>
              {saving ? "Saving..." : "Save"}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  )
}
