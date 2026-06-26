import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { t } from "@/i18n";

export function SupportBanner() {
  return (
    <Alert className="m-4 mb-0">
      <AlertTitle className="flex items-center gap-2">
        {t("frontend.support_banner.title")} <Badge variant="secondary">{t("frontend.support_banner.starter_badge")}</Badge>
      </AlertTitle>
      <AlertDescription>
        {t("frontend.support_banner.description")}
      </AlertDescription>
    </Alert>
  );
}
