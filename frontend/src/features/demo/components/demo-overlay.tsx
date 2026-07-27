import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { t } from "@/i18n";

interface DemoOverlayProps {
  onRetry: () => void;
}

export function DemoOverlay({ onRetry }: DemoOverlayProps) {
  return (
    <Dialog
      open
      onOpenChange={(open) => {
        if (!open) onRetry();
      }}
    >
      <DialogContent
        showCloseButton={false}
        aria-modal="true"
        aria-describedby="demo-overlay-description"
        data-testid="demo-overlay"
        className="max-w-sm text-center"
      >
        <DialogHeader className="text-center">
          <DialogTitle>{t("frontend.demo.overlay.message")}</DialogTitle>
          <DialogDescription id="demo-overlay-description">
            {t("frontend.demo.overlay.description")}
          </DialogDescription>
        </DialogHeader>
        <DialogFooter className="sm:justify-center">
          <Button onClick={onRetry}>{t("frontend.demo.overlay.retry")}</Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
