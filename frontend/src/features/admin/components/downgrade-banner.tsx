import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { t } from "@/i18n";

export function DowngradeBanner() {
  return (
    <Alert className="m-4 mb-0" data-testid="downgrade-banner">
      <AlertTitle>{t("frontend.plan.downgrade_title")}</AlertTitle>
      <AlertDescription>{t("frontend.plan.downgrade_description")}</AlertDescription>
    </Alert>
  );
}
