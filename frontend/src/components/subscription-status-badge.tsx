import { Badge } from "@/components/ui/badge";
import { t } from "@/i18n";

const STATUS_CONFIG: Record<string, { labelKey: string; className: string }> = {
  active: {
    labelKey: "frontend.subscriptions.status_active",
    className:
      "border-green-200 bg-green-50 text-green-700 dark:border-green-800 dark:bg-green-950 dark:text-green-400",
  },
  inactive: {
    labelKey: "frontend.subscriptions.status_inactive",
    className:
      "border-red-200 bg-red-50 text-red-700 dark:border-red-800 dark:bg-red-950 dark:text-red-400",
  },
  expired: {
    labelKey: "frontend.subscriptions.status_expired",
    className:
      "border-amber-200 bg-amber-50 text-amber-700 dark:border-amber-800 dark:bg-amber-950 dark:text-amber-400",
  },
  cancelled: {
    labelKey: "frontend.subscriptions.status_cancelled",
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
      {config ? t(config.labelKey) : status}
    </Badge>
  );
}
