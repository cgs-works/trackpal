import { Card, CardContent } from "@/components/ui/card";
import { Building2, CheckCircle2, XCircle } from "lucide-react";

interface SummaryCardsProps {
  total: number
  active: number
  inactive: number
}

export function SummaryCards({ total, active, inactive }: SummaryCardsProps) {
  return (
    <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
      <SummaryCard
        icon={<Building2 className="size-5 text-muted-foreground" />}
        label="Total Businesses"
        value={total}
      />
      <SummaryCard
        icon={<CheckCircle2 className="size-5 text-emerald-600 dark:text-emerald-400" />}
        label="Active"
        value={active}
      />
      <SummaryCard
        icon={<XCircle className="size-5 text-amber-600 dark:text-amber-400" />}
        label="Inactive"
        value={inactive}
      />
    </div>
  )
}

function SummaryCard({
  icon,
  label,
  value,
}: {
  icon: React.ReactNode
  label: string
  value: number
}) {
  return (
    <Card>
      <CardContent className="flex items-center gap-4 p-5">
        <div className="flex size-10 shrink-0 items-center justify-center rounded-lg bg-muted">
          {icon}
        </div>
        <div>
          <p className="text-sm text-muted-foreground">{label}</p>
          <p className="text-2xl font-bold tracking-tight">{value}</p>
        </div>
      </CardContent>
    </Card>
  )
}
