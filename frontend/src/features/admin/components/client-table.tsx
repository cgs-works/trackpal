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
import { Pencil, Trash2, Power, CreditCard } from "lucide-react";
import type { Client } from "../services/client-api";

interface ClientTableProps {
  clients: Client[];
  onEdit: (client: Client) => void;
  onDelete: (client: Client) => void;
  onToggleStatus: (client: Client) => void;
  onViewSubscriptions: (client: Client) => void;
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
  );
}

export function ClientTable({
  clients,
  onEdit,
  onDelete,
  onToggleStatus,
  onViewSubscriptions,
}: ClientTableProps) {
  return (
    <>
      {/* Desktop table */}
      <div className="hidden md:block overflow-x-auto">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Name</TableHead>
              <TableHead>Username</TableHead>
              <TableHead>Phone</TableHead>
              <TableHead>Status</TableHead>
              <TableHead className="text-right">Actions</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {clients.map((client) => (
              <TableRow
                key={client.id}
                className="hover:bg-muted/50 transition-colors"
              >
                <TableCell className="font-medium">
                  {client.full_name}
                </TableCell>
                <TableCell>
                  <Badge variant="outline" className="font-mono">
                    {client.username}
                  </Badge>
                </TableCell>
                <TableCell className="text-muted-foreground">
                  {client.phone || "—"}
                </TableCell>
                <TableCell>
                  <StatusBadge active={client.is_active} />
                </TableCell>
                <TableCell className="text-right">
                  <div className="flex items-center justify-end gap-1">
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() => onEdit(client)}
                      title="Edit"
                    >
                      <Pencil className="size-3.5" />
                      <span className="sr-only">Edit</span>
                    </Button>
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() => onViewSubscriptions(client)}
                      title="Subscriptions"
                    >
                      <CreditCard className="size-3.5" />
                      <span className="sr-only">Subscriptions</span>
                    </Button>
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() => onToggleStatus(client)}
                      title={client.is_active ? "Deactivate" : "Activate"}
                    >
                      <Power className="size-3.5" />
                      <span className="sr-only">
                        {client.is_active ? "Deactivate" : "Activate"}
                      </span>
                    </Button>
                    <Button
                      variant="ghost"
                      size="sm"
                      className="text-destructive hover:text-destructive"
                      onClick={() => onDelete(client)}
                      disabled={client.is_active}
                      title={
                        client.is_active
                          ? "Deactivate first to delete"
                          : "Delete"
                      }
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
        {clients.map((client) => (
          <div key={client.id} className="p-4 flex flex-col gap-2">
            <div className="flex items-start justify-between">
              <div>
                <p className="font-medium">{client.full_name}</p>
                <p className="text-sm text-muted-foreground font-mono">
                  {client.username}
                </p>
              </div>
              <StatusBadge active={client.is_active} />
            </div>
            <div className="text-sm text-muted-foreground">
              <p>Phone: {client.phone || "—"}</p>
            </div>
            <Separator />
            <div className="flex items-center gap-1">
              <Button variant="ghost" size="sm" onClick={() => onEdit(client)}>
                <Pencil className="size-3.5 mr-1" />
                Edit
              </Button>
              <Button
                variant="ghost"
                size="sm"
                onClick={() => onViewSubscriptions(client)}
              >
                <CreditCard className="size-3.5 mr-1" />
                Subscriptions
              </Button>
              <Button
                variant="ghost"
                size="sm"
                onClick={() => onToggleStatus(client)}
              >
                <Power className="size-3.5 mr-1" />
                {client.is_active ? "Deactivate" : "Activate"}
              </Button>
              <Button
                variant="ghost"
                size="sm"
                className="text-destructive hover:text-destructive"
                onClick={() => onDelete(client)}
                disabled={client.is_active}
              >
                <Trash2 className="size-3.5 mr-1" />
                Delete
              </Button>
            </div>
          </div>
        ))}
      </div>
    </>
  );
}
