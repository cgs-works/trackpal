import { useState } from "react";
import { HelpCircle } from "lucide-react";
import { Button } from "@/components/ui/button";
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetHeader,
  SheetTitle,
} from "@/components/ui/sheet";
import { t } from "@/i18n";
import {
  HELP_TARGET_CONTRACT_VERSION,
  isPrivateHelpEnabled,
} from "../config";
import { findActiveHelpTarget } from "../help-targets";
import {
  getHelpIndex,
  getHelpTopic,
  type HelpTopic,
} from "../services/help-api";
import { SafeMarkdown } from "./safe-markdown";
import { SafeNavigationLink } from "./help-center-page";

export function ContextualHelpSheet() {
  const [open, setOpen] = useState(false);
  const [topic, setTopic] = useState<HelpTopic | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(false);

  if (!isPrivateHelpEnabled()) {
    return null;
  }

  async function openHelp() {
    setOpen(true);
    setTopic(null);
    setLoading(true);
    setError(false);

    try {
      const target = findActiveHelpTarget();
      if (!target) {
        throw new Error("No Help target is present on this screen.");
      }

      const index = await getHelpIndex();
      if (index.frontend_target_contract_version !== HELP_TARGET_CONTRACT_VERSION) {
        throw new Error("The Help target contract is not compatible.");
      }

      const summary = index.topics.find((item) => item.help_targets.includes(target));
      if (!summary) {
        throw new Error("No authorized Help topic matches this screen.");
      }
      setTopic(await getHelpTopic(summary.id));
    } catch {
      setError(true);
    } finally {
      setLoading(false);
    }
  }

  function handleOpenChange(nextOpen: boolean) {
    setOpen(nextOpen);
    if (!nextOpen) {
      window.setTimeout(() => {
        document
          .querySelector<HTMLButtonElement>('[data-testid="contextual-help-trigger"]')
          ?.focus();
      }, 0);
    }
  }

  return (
    <>
      <Button
        data-testid="contextual-help-trigger"
        variant="outline"
        size="sm"
        aria-label={t("frontend.help.about_screen")}
        onClick={() => void openHelp()}
      >
        <HelpCircle data-icon="inline-start" />
        {t("frontend.help.about_screen")}
      </Button>

      <Sheet open={open} onOpenChange={handleOpenChange}>
        <SheetContent
          side="right"
          className="w-[min(100vw,32rem)] max-w-full"
          data-testid="contextual-help-sheet"
        >
          <SheetHeader>
            <SheetTitle>{topic?.title ?? t("frontend.help.about_screen")}</SheetTitle>
            <SheetDescription>
              {topic?.summary ?? t("frontend.help.contextual_description")}
            </SheetDescription>
          </SheetHeader>
          <div className="min-h-0 overflow-y-auto px-4 pb-6">
            {loading && <p className="text-sm text-muted-foreground">{t("frontend.help.loading")}</p>}
            {!loading && error && (
              <div className="flex flex-col gap-3">
                <p className="text-sm text-muted-foreground">{t("frontend.help.contextual_error")}</p>
                <Button variant="outline" size="sm" onClick={() => void openHelp()}>
                  {t("frontend.help.retry")}
                </Button>
              </div>
            )}
            {!loading && !error && topic && (
              <div className="flex flex-col gap-6">
                <SafeMarkdown source={topic.body} />
                <SafeNavigationLink topic={topic} />
              </div>
            )}
          </div>
        </SheetContent>
      </Sheet>
    </>
  );
}
