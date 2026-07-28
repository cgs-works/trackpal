import { BrandLogo } from "@/components/layout/brand-logo";
import { cn } from "@/lib/utils";
import { t } from "@/i18n/public";

const PRIVACY_POLICY_URL = "https://trackpal.wilfredocamacho.dev/privacy-policy";
const TERMS_OF_SERVICE_URL = "https://trackpal.wilfredocamacho.dev/terms-of-service";

interface LegalFooterProps {
  className?: string;
}

export function LegalFooter({ className }: LegalFooterProps) {
  return (
    <footer
      className={cn(
        "flex w-full flex-col items-center gap-3 border-t border-border/60 pt-4 sm:flex-row sm:justify-between",
        className,
      )}
      aria-label={t("legal.footer_label")}
    >
      <div className="flex flex-col items-center gap-1 sm:items-start">
        <BrandLogo className="h-5 w-[90px]" />
        <p className="text-center text-[11px] text-muted-foreground sm:text-left">
          {t("legal.copyright")}
        </p>
      </div>
      <nav
        className="flex flex-wrap items-center justify-center gap-x-4 gap-y-2"
        aria-label={t("legal.footer_label")}
      >
        <a
          href={PRIVACY_POLICY_URL}
          className="inline-flex min-h-10 items-center rounded-sm px-1 text-xs text-muted-foreground transition-colors hover:text-foreground focus-visible:outline-none focus-visible:ring-3 focus-visible:ring-ring/50"
        >
          {t("legal.privacy_policy")}
        </a>
        <a
          href={TERMS_OF_SERVICE_URL}
          className="inline-flex min-h-10 items-center rounded-sm px-1 text-xs text-muted-foreground transition-colors hover:text-foreground focus-visible:outline-none focus-visible:ring-3 focus-visible:ring-ring/50"
        >
          {t("legal.terms_of_service")}
        </a>
      </nav>
    </footer>
  );
}
