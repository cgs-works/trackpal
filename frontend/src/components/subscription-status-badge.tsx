import { Badge } from "@/components/ui/badge";

const STATUS_CONFIG: Record<string, { label: string; className: string }> = {
  active: {
    label: "Active",
    className:
      "border-green-200 bg-green-50 text-green-700 dark:border-green-800 dark:bg-green-950 dark:text-green-400",
  },
  inactive: {
    label: "Inactive",
    className:
      "border-red-200 bg-red-50 text-red-700 dark:border-red-800 dark:bg-red-950 dark:text-red-400",
  },
  expired: {
    label: "Expired",
    className:
      "border-amber-200 bg-amber-50 text-amber-700 dark:border-amber-800 dark:bg-amber-950 dark:text-amber-400",
  },
  cancelled: {
    label: "Cancelled",
    className:
      "border-gray-200 bg-gray-50 text-gray-600 dark:border-gray-700 dark:bg-gray-900 dark:text-gray-400",
  },
};

export function SubscriptionStatusBadge({
  status,
}: {
  status: string;
}) {
  const config = STATUS_CONFIG[status];
  return (
    <Badge variant="outline" className={config?.className}>
      {config?.label || status}
    </Badge>
  );
}
