import { Button } from "@/components/ui/button";
import { Plus } from "lucide-react";

interface EmptyStateProps {
  isSearch: boolean
  onAction?: () => void
  actionLabel?: string
}

export function EmptyState({ isSearch, onAction, actionLabel }: EmptyStateProps) {
  return (
    <div className="flex flex-col items-center justify-center py-16 text-center">
      <div className="flex size-12 items-center justify-center rounded-full bg-muted mb-4">
        <Plus className="size-6 text-muted-foreground" />
      </div>
      <p className="text-muted-foreground mb-4">
        {isSearch ? "No businesses match your search" : "No businesses yet"}
      </p>
      {!isSearch && onAction && (
        <Button size="sm" onClick={onAction}>
          <Plus className="size-4 mr-1.5" />
          {actionLabel || "Create your first business"}
        </Button>
      )}
    </div>
  )
}
