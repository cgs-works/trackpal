import { Button } from "@/components/ui/button";
import { t } from "@/i18n";

interface DemoOverlayProps {
  onRetry: () => void;
}

export function DemoOverlay({ onRetry }: DemoOverlayProps) {
  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-background/80 p-4 backdrop-blur-sm"
      role="dialog"
      aria-modal="true"
      aria-labelledby="demo-overlay-title"
      data-testid="demo-overlay"
    >
      <div className="mx-4 max-w-sm rounded-lg border bg-card p-6 text-center shadow-lg">
        <h2
          id="demo-overlay-title"
          className="text-sm font-medium text-foreground"
        >
          {t("frontend.demo.overlay.message")}
        </h2>
        <Button className="mt-4" onClick={onRetry}>
          {t("frontend.demo.overlay.retry")}
        </Button>
      </div>
    </div>
  );
}
