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
        icon={<Building2 className="size-5" />}
        label="Total Businesses"
        value={total}
      />
      <SummaryCard
        icon={<CheckCircle2 className="size-5" />}
        label="Active"
        value={active}
      />
      <SummaryCard
        icon={<XCircle className="size-5" />}
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
    <Card className="shadow-none">
      <CardContent className="flex items-center gap-4 p-5">
        <div className="flex size-10 shrink-0 items-center justify-center rounded-lg border bg-primary/8 text-primary">
          {icon}
        </div>
        <div>
          <p className="text-sm text-muted-foreground">{label}</p>
          <p className="font-mono text-2xl font-semibold tracking-tight">{value}</p>
        </div>
      </CardContent>
    </Card>
  )
}
