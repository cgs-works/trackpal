import { CheckCircle2, XCircle } from "lucide-react"

interface StatusBarProps {
  total: number
  active: number
  inactive: number
}

export function StatusBar({ total, active, inactive }: StatusBarProps) {
  return (
    <div className="flex items-center gap-4 text-sm">
      <div className="flex items-center gap-1.5">
        <span className="font-medium text-foreground">{total}</span>
        <span className="text-muted-foreground">businesses</span>
      </div>
      <span className="text-muted-foreground/40">·</span>
      <div className="flex items-center gap-1.5">
        <CheckCircle2 className="h-3.5 w-3.5 text-emerald-600 dark:text-emerald-400" />
        <span className="font-medium text-foreground">{active}</span>
        <span className="text-muted-foreground">active</span>
      </div>
      <span className="text-muted-foreground/40">·</span>
      <div className="flex items-center gap-1.5">
        <XCircle className="h-3.5 w-3.5 text-amber-600 dark:text-amber-400" />
        <span className="font-medium text-foreground">{inactive}</span>
        <span className="text-muted-foreground">inactive</span>
      </div>
    </div>
  )
}
