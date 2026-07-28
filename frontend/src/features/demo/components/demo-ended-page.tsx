import { t } from "@/i18n/public";
import { LegalFooter } from "@/components/layout/legal-footer";
import { MessageCircle, Send, Mail } from "lucide-react";

const WHATSAPP_URL = "https://wa.me/584243106642";
const TELEGRAM_URL = "https://t.me/trackpal";

function ContactLinks() {
  return (
    <div className="flex flex-col gap-3">
      <a
        href={WHATSAPP_URL}
        target="_blank"
        rel="noopener noreferrer"
        className="inline-flex min-h-10 items-center justify-center gap-2 rounded-lg bg-primary px-4 py-2.5 text-sm font-medium text-primary-foreground transition-colors hover:bg-primary/90 focus-visible:outline-none focus-visible:ring-3 focus-visible:ring-ring/50"
      >
        <MessageCircle className="size-4" aria-hidden="true" />
        {t("demo_ended.contact.whatsapp")}
      </a>
      <div className="flex gap-3">
        <a
          href={TELEGRAM_URL}
          target="_blank"
          rel="noopener noreferrer"
          className="inline-flex min-h-10 flex-1 items-center justify-center gap-2 rounded-lg border px-3 py-2 text-sm font-medium text-foreground transition-colors hover:bg-muted focus-visible:outline-none focus-visible:ring-3 focus-visible:ring-ring/50"
        >
          <Send className="size-4" aria-hidden="true" />
          {t("demo_ended.contact.telegram")}
        </a>
        <a
          href="mailto:hola@trackpal.app"
          className="inline-flex min-h-10 flex-1 items-center justify-center gap-2 rounded-lg border px-3 py-2 text-sm font-medium text-foreground transition-colors hover:bg-muted focus-visible:outline-none focus-visible:ring-3 focus-visible:ring-ring/50"
        >
          <Mail className="size-4" aria-hidden="true" />
          {t("demo_ended.contact.email")}
        </a>
      </div>
    </div>
  );
}

export function DemoEndedPage() {
  return (
    <div className="flex min-h-screen flex-col bg-background">
      <main
        className="flex flex-1 items-center justify-center px-4 py-8"
        aria-labelledby="demo-ended-title"
        aria-describedby="demo-ended-description"
      >
        <div className="w-full max-w-md space-y-6 text-center">
          <div className="space-y-2">
            <h1 id="demo-ended-title" className="text-2xl font-semibold text-foreground">
              {t("demo_ended.title")}
            </h1>
            <p id="demo-ended-description" className="text-muted-foreground">
              {t("demo_ended.description")}
            </p>
          </div>
          <ContactLinks />
        </div>
      </main>
      <div className="px-4 pb-8">
        <LegalFooter className="mx-auto max-w-md" />
      </div>
    </div>
  );
}
