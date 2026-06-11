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

export interface ClientForm {
  id: string | null;
  full_name: string;
  local_username: string;
  phone: string;
  password: string;
}

export function getEmptyForm(): ClientForm {
  return {
    id: null,
    full_name: "",
    local_username: "",
    phone: "",
    password: "",
  };
}

interface ClientFormDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  mode: "create" | "edit";
  form: ClientForm;
  onFormChange: (key: keyof ClientForm, value: string) => void;
  onSubmit: (e: React.FormEvent) => void;
  saving: boolean;
  error: string;
}

export function ClientFormDialog({
  open,
  onOpenChange,
  mode,
  form,
  onFormChange,
  onSubmit,
  saving,
  error,
}: ClientFormDialogProps) {
  const isEdit = mode === "edit";
  const title = isEdit ? "Edit Client" : "Create Client";

  return (
    <Dialog
      open={open}
      onOpenChange={(o) => {
        if (!o) onOpenChange(o);
      }}
    >
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>{title}</DialogTitle>
          <DialogDescription>
            {isEdit
              ? "Update client details and contact information."
              : "Register a new client for your business."}
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

          <div className="flex flex-col gap-2">
            <Label htmlFor="local_username">Username</Label>
            <Input
              id="local_username"
              required
              value={form.local_username}
              onChange={(e) => onFormChange("local_username", e.target.value)}
            />
            <p className="text-xs text-muted-foreground">
              Unique identifier for client login
            </p>
          </div>

          <div className="flex flex-col gap-2">
            <Label htmlFor="phone">Phone</Label>
            <Input
              id="phone"
              type="tel"
              value={form.phone}
              onChange={(e) => onFormChange("phone", e.target.value)}
            />
          </div>

          {!isEdit && (
            <div className="flex flex-col gap-2">
              <Label htmlFor="password">Password</Label>
              <Input
                id="password"
                type="password"
                autoComplete="new-password"
                required
                value={form.password}
                onChange={(e) => onFormChange("password", e.target.value)}
              />
            </div>
          )}

          <DialogFooter>
            <Button
              type="button"
              variant="outline"
              onClick={() => onOpenChange(false)}
              disabled={saving}
            >
              Cancel
            </Button>
            <Button type="submit" disabled={saving}>
              {saving ? "Saving..." : "Save"}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
