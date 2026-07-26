import { t } from "@/i18n/public";
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
        className="inline-flex items-center justify-center gap-2 rounded-md bg-green-600 px-4 py-2.5 text-sm font-medium text-white transition-colors hover:bg-green-700 focus:outline-none focus:ring-2 focus:ring-green-500 focus:ring-offset-2"
      >
        <MessageCircle className="size-4" aria-hidden="true" />
        {t("demo_ended.contact.whatsapp")}
      </a>
      <div className="flex gap-3">
        <a
          href={TELEGRAM_URL}
          target="_blank"
          rel="noopener noreferrer"
          className="inline-flex flex-1 items-center justify-center gap-2 rounded-md border px-3 py-2 text-sm font-medium text-foreground transition-colors hover:bg-muted focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-2"
        >
          <Send className="size-4" aria-hidden="true" />
          {t("demo_ended.contact.telegram")}
        </a>
        <a
          href="mailto:hola@trackpal.app"
          className="inline-flex flex-1 items-center justify-center gap-2 rounded-md border px-3 py-2 text-sm font-medium text-foreground transition-colors hover:bg-muted focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-2"
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
    <div className="min-h-screen flex items-center justify-center bg-background px-4">
      <div className="w-full max-w-md text-center space-y-6">
        <div className="space-y-2">
          <h1 className="text-2xl font-semibold text-foreground">
            {t("demo_ended.title")}
          </h1>
          <p className="text-muted-foreground">
            {t("demo_ended.description")}
          </p>
        </div>
        <ContactLinks />
      </div>
    </div>
  );
}
