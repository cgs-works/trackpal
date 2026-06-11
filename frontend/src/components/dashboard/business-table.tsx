import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Separator } from "@/components/ui/separator";
import { Pencil, Trash2, Power, Settings } from "lucide-react";

interface Tenant {
  id: string
  full_name: string
  client_prefix: string
  email: string | null
  phone: string | null
  evolution_instance_name: string | null
  is_active: boolean
}

interface BusinessTableProps {
  tenants: Tenant[]
  onEdit: (tenant: Tenant) => void
  onDelete: (tenant: Tenant) => void
  onToggleStatus: (tenant: Tenant) => void
  onManageCatalog: (tenant: Tenant) => void
}

function StatusBadge({ active }: { active: boolean }) {
  return (
    <Badge
      variant={active ? "default" : "secondary"}
      className={
        active
          ? "bg-emerald-100 text-emerald-800 hover:bg-emerald-100 dark:bg-emerald-900 dark:text-emerald-300"
          : "bg-amber-100 text-amber-800 hover:bg-amber-100 dark:bg-amber-900 dark:text-amber-300"
      }
    >
      {active ? "Active" : "Inactive"}
    </Badge>
  )
}

export function BusinessTable({
  tenants,
  onEdit,
  onDelete,
  onToggleStatus,
  onManageCatalog,
}: BusinessTableProps) {
  return (
    <>
      {/* Desktop table */}
      <div className="hidden md:block overflow-x-auto">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Business</TableHead>
              <TableHead>Prefix</TableHead>
              <TableHead>Contact</TableHead>
              <TableHead>Instance</TableHead>
              <TableHead>Status</TableHead>
              <TableHead className="text-right">Actions</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {tenants.map((tenant) => (
              <TableRow key={tenant.id} className="hover:bg-muted/50 transition-colors">
                <TableCell className="font-medium">{tenant.full_name}</TableCell>
                <TableCell>
                  <Badge variant="outline" className="font-mono">
                    {tenant.client_prefix || "—"}
                  </Badge>
                </TableCell>
                <TableCell>
                  <div className="text-sm">
                    <div>{tenant.email}</div>
                    {tenant.phone && (
                      <div className="text-muted-foreground">{tenant.phone}</div>
                    )}
                  </div>
                </TableCell>
                <TableCell className="text-muted-foreground text-sm">
                  {tenant.evolution_instance_name || "—"}
                </TableCell>
                <TableCell>
                  <StatusBadge active={tenant.is_active} />
                </TableCell>
                <TableCell className="text-right">
                  <div className="flex items-center justify-end gap-1">
                    <Button variant="ghost" size="sm" onClick={() => onEdit(tenant)} title="Edit">
                      <Pencil className="size-3.5" />
                      <span className="sr-only">Edit</span>
                    </Button>
                    <Button variant="ghost" size="sm" onClick={() => onManageCatalog(tenant)} title="Manage catalog">
                      <Settings className="size-3.5" />
                      <span className="sr-only">Manage catalog</span>
                    </Button>
                    <Button variant="ghost" size="sm" onClick={() => onToggleStatus(tenant)} title={tenant.is_active ? "Deactivate" : "Activate"}>
                      <Power className="size-3.5" />
                      <span className="sr-only">{tenant.is_active ? "Deactivate" : "Activate"}</span>
                    </Button>
                    <Button
                      variant="ghost"
                      size="sm"
                      className="text-destructive hover:text-destructive"
                      onClick={() => onDelete(tenant)}
                      disabled={tenant.is_active}
                      title={tenant.is_active ? "Deactivate first to delete" : "Delete"}
                    >
                      <Trash2 className="size-3.5" />
                      <span className="sr-only">Delete</span>
                    </Button>
                  </div>
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </div>

      {/* Mobile card list */}
      <div className="md:hidden divide-y">
        {tenants.map((tenant) => (
          <div key={tenant.id} className="p-4 flex flex-col gap-2">
            <div className="flex items-start justify-between">
              <div>
                <p className="font-medium">{tenant.full_name}</p>
                <p className="text-sm text-muted-foreground">{tenant.email}</p>
              </div>
              <StatusBadge active={tenant.is_active} />
            </div>
            <div className="text-sm text-muted-foreground">
              <p>Prefix: {tenant.client_prefix || "—"}</p>
              <p>Phone: {tenant.phone || "—"}</p>
              <p>Instance: {tenant.evolution_instance_name || "—"}</p>
            </div>
            <Separator />
            <div className="flex items-center gap-1">
              <Button variant="ghost" size="sm" onClick={() => onEdit(tenant)}>
                <Pencil className="size-3.5 mr-1" />
                Edit
              </Button>
              <Button variant="ghost" size="sm" onClick={() => onManageCatalog(tenant)}>
                <Settings className="size-3.5 mr-1" />
                Catalog
              </Button>
              <Button variant="ghost" size="sm" onClick={() => onToggleStatus(tenant)}>
                <Power className="size-3.5 mr-1" />
                {tenant.is_active ? "Deactivate" : "Activate"}
              </Button>
              <Button
                variant="ghost"
                size="sm"
                className="text-destructive hover:text-destructive"
                onClick={() => onDelete(tenant)}
                disabled={tenant.is_active}
              >
                <Trash2 className="size-3.5 mr-1" />
                Delete
              </Button>
            </div>
          </div>
        ))}
      </div>
    </>
  )
}
