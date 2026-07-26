import { t } from "@/i18n";

export function DemoOverlay() {
  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-background/80 backdrop-blur-sm"
      role="alert"
      aria-live="assertive"
      data-testid="demo-overlay"
    >
      <div className="rounded-lg border bg-card p-6 text-center shadow-lg max-w-sm mx-4">
        <p className="text-sm font-medium text-foreground">
          {t("frontend.demo.overlay.message")}
        </p>
      </div>
    </div>
  );
}
