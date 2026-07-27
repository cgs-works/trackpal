import { Copy, Eye, KeyRound, Trash2 } from "lucide-react";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { t } from "@/i18n";

export function DemoPublicApiCard() {
  return (
    <div className="flex flex-col gap-4 rounded-xl border bg-card p-4">
      <div className="flex flex-col gap-1">
        <div className="flex items-center gap-2">
          <h2 className="text-base font-medium" aria-describedby="public-api-demo-tooltip">
            {t("frontend.public_api.section_title")}
          </h2>
          <span
            aria-hidden="true"
            title={t("frontend.public_api.tooltip")}
            className="inline-flex size-5 items-center justify-center rounded-full border text-xs text-muted-foreground"
          >
            ?
          </span>
          <span id="public-api-demo-tooltip" className="sr-only">
            {t("frontend.public_api.tooltip")}
          </span>
        </div>
        <p className="text-sm text-muted-foreground">
          {t("frontend.public_api.description")}
        </p>
      </div>

      <Alert>
        <KeyRound className="size-4" />
        <AlertTitle>{t("frontend.public_api.demo_title")}</AlertTitle>
        <AlertDescription>{t("frontend.public_api.demo_description")}</AlertDescription>
      </Alert>

      <div className="flex flex-col gap-3 rounded-lg border bg-background p-3" aria-disabled="true">
        <div>
          <Label htmlFor="public-api-demo-site">{t("frontend.public_api.site_label")}</Label>
          <p className="text-xs text-muted-foreground">
            {t("frontend.public_api.demo_controls_disabled")}
          </p>
        </div>
        <div className="flex flex-col gap-2 sm:flex-row">
          <Input
            id="public-api-demo-site"
            disabled
            placeholder={t("frontend.public_api.demo_origin_placeholder")}
          />
          <Button type="button" disabled>
            {t("frontend.public_api.create_key")}
          </Button>
        </div>
      </div>

      <div className="flex flex-col gap-3 rounded-lg border bg-background p-3" aria-disabled="true">
        <Label htmlFor="public-api-demo-key">{t("frontend.public_api.key_label")}</Label>
        <Input
          id="public-api-demo-key"
          disabled
          placeholder={t("frontend.public_api.demo_key_unavailable")}
        />
        <div className="flex flex-wrap gap-2">
          <Button type="button" variant="outline" disabled>
            <Eye data-icon="inline-start" />
            {t("frontend.public_api.show")}
          </Button>
          <Button type="button" variant="outline" disabled>
            <Copy data-icon="inline-start" />
            {t("frontend.public_api.copy")}
          </Button>
          <Button type="button" variant="destructive" disabled>
            <Trash2 data-icon="inline-start" />
            {t("frontend.public_api.delete_key")}
          </Button>
        </div>
      </div>
    </div>
  );
}
