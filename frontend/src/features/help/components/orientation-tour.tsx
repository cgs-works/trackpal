import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";
import { useNavigate } from "@tanstack/react-router";
import {
  ACTIONS,
  EVENTS,
  STATUS,
  Joyride,
  type EventHandler,
  type Step,
  type TooltipRenderProps,
} from "react-joyride";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog";
import { t } from "@/i18n";
import { useAuthStore } from "@/store/auth";
import { resolveSafeHelpNavigation } from "../safe-navigation";
import {
  acknowledgeHelpTour,
  getUnseenHelpTour,
  replayHelpTour,
  type HelpTourRelease,
} from "../services/help-api";
import { HELP_TARGET_CONTRACT_VERSION, isPrivateHelpEnabled } from "../config";
import { SafeMarkdown } from "./safe-markdown";

export const HELP_TOUR_REPLAY_EVENT = "trackpal:help-tour-replay";

export function requestHelpTourReplay() {
  window.dispatchEvent(new Event(HELP_TOUR_REPLAY_EVENT));
}

type TourContextValue = { requestSkip: () => void };
const TourContext = createContext<TourContextValue | null>(null);

function TourTooltip(props: TooltipRenderProps) {
  const context = useContext(TourContext);
  const { step, index, size, isLastStep, continuous, tooltipProps } = props;
  const [isMobile, setIsMobile] = useState(false);

  useEffect(() => {
    const media = window.matchMedia?.("(max-width: 767px)");
    if (!media) return;
    const update = () => setIsMobile(media.matches);
    update();
    media.addEventListener?.("change", update);
    return () => media.removeEventListener?.("change", update);
  }, []);

  const skipProps = {
    ...props.skipProps,
    onClick: (event: React.MouseEvent<HTMLButtonElement>) => {
      event.preventDefault();
      context?.requestSkip();
    },
  };

  return (
    <div
      {...tooltipProps}
      style={
        isMobile
          ? {
              position: "fixed",
              top: "auto",
              right: "1rem",
              bottom: "1rem",
              left: "1rem",
              transform: "none",
            }
          : undefined
      }
      data-testid="help-tour-popover"
      className="z-[1000] max-w-lg rounded-xl border bg-popover p-5 text-popover-foreground shadow-xl"
      aria-labelledby="help-tour-title"
    >
      <div className="flex items-start justify-between gap-4">
        <div>
          <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
            {t("frontend.help.tour_step", { current: index + 1, total: size })}
          </p>
          <h2 id="help-tour-title" className="mt-1 font-heading text-lg font-semibold">
            {step.title}
          </h2>
        </div>
        <Button
          {...props.closeProps}
          type="button"
          variant="ghost"
          size="icon"
          aria-label={t("frontend.help.tour_close")}
          onClick={(event) => {
            event.preventDefault();
            context?.requestSkip();
          }}
        >
          <span aria-hidden="true">×</span>
        </Button>
      </div>
      <div className="mt-3 max-h-48 overflow-y-auto text-sm leading-6">
        <SafeMarkdown source={String(step.content)} />
      </div>
      <div className="mt-5 flex flex-wrap items-center justify-between gap-2">
        <Button {...skipProps} type="button" variant="ghost" size="sm">
          {t("frontend.help.tour_skip")}
        </Button>
        <div className="flex gap-2">
          {index > 0 && (
            <Button {...props.backProps} type="button" variant="outline" size="sm">
              {t("frontend.help.tour_back")}
            </Button>
          )}
          {continuous && (
            <Button {...props.primaryProps} type="button" size="sm">
              {isLastStep
                ? t("frontend.help.tour_done")
                : t("frontend.help.tour_next")}
            </Button>
          )}
        </div>
      </div>
    </div>
  );
}

function useReducedMotion(): boolean {
  const [reducedMotion, setReducedMotion] = useState(false);

  useEffect(() => {
    const media = window.matchMedia?.("(prefers-reduced-motion: reduce)");
    if (!media) return;
    const update = () => setReducedMotion(media.matches);
    update();
    media.addEventListener?.("change", update);
    return () => media.removeEventListener?.("change", update);
  }, []);

  return reducedMotion;
}

function tourSelector(target: string): string {
  return `[data-help-id="${target}"]`;
}

export function OrientationTour() {
  const { isAuthenticated, role, isMasterSupportContext } = useAuthStore();
  const navigate = useNavigate();
  const reducedMotion = useReducedMotion();
  const [tour, setTour] = useState<HelpTourRelease | null>(null);
  const [stepIndex, setStepIndex] = useState(0);
  const [running, setRunning] = useState(false);
  const [skipConfirmationOpen, setSkipConfirmationOpen] = useState(false);
  const [acknowledging, setAcknowledging] = useState(false);

  const canRun =
    isPrivateHelpEnabled() &&
    isAuthenticated &&
    role === "tenant" &&
    !isMasterSupportContext;

  const loadTour = useCallback(
    async (loader: () => Promise<HelpTourRelease>) => {
      try {
        const nextTour = await loader();
        if (
          nextTour.frontend_target_contract_version !==
          HELP_TARGET_CONTRACT_VERSION
        ) {
          return;
        }
        setTour(nextTour);
        setStepIndex(0);
        setRunning(true);
      } catch {
        // Help is optional and must not make the product unavailable.
      }
    },
    [],
  );

  useEffect(() => {
    if (!canRun) {
      setTour(null);
      setRunning(false);
      return;
    }
    void loadTour(getUnseenHelpTour);
  }, [canRun, loadTour]);

  useEffect(() => {
    if (!canRun) return;
    const handleReplay = () => {
      void loadTour(async () => {
        const current = tour;
        if (current) return replayHelpTour(current.release_id);
        const unseen = await getUnseenHelpTour();
        return replayHelpTour(unseen.release_id);
      });
    };
    window.addEventListener(HELP_TOUR_REPLAY_EVENT, handleReplay);
    return () => window.removeEventListener(HELP_TOUR_REPLAY_EVENT, handleReplay);
  }, [canRun, loadTour, tour]);

  useEffect(() => {
    if (!running || !tour) return;
    const step = tour.steps[stepIndex];
    if (!step) return;
    const destination = resolveSafeHelpNavigation(
      { route: step.route, settings_category: step.settings_category },
      "tenant",
    );
    if (!destination) {
      setRunning(false);
      return;
    }
    if (destination.to === "/admin/settings") {
      void navigate({ to: destination.to, search: destination.search });
    } else {
      void navigate({ to: destination.to });
    }
  }, [navigate, running, stepIndex, tour]);

  const acknowledge = useCallback(
    async (status: "completed" | "skipped") => {
      if (!tour || acknowledging) return;
      setAcknowledging(true);
      try {
        await acknowledgeHelpTour(tour.release_id, status);
        setRunning(false);
        setTour(null);
      } catch {
        toast.error(t("frontend.help.tour_acknowledge_error"));
      } finally {
        setAcknowledging(false);
      }
    },
    [acknowledging, tour],
  );

  const handleEvent: EventHandler = useCallback(
    (data) => {
      if (data.type === EVENTS.STEP_AFTER) {
        const nextIndex = data.action === ACTIONS.PREV ? data.index - 1 : data.index + 1;
        setStepIndex(Math.max(0, nextIndex));
      }
      if (data.type === EVENTS.ERROR) {
        setRunning(false);
      }
      if (data.status === STATUS.FINISHED) {
        void acknowledge("completed");
      }
      if (data.status === STATUS.SKIPPED) {
        setRunning(false);
        setSkipConfirmationOpen(true);
      }
    },
    [acknowledge],
  );

  const steps = useMemo<Step[]>(
    () =>
      tour?.steps.map((step) => ({
        target: tourSelector(step.target),
        title: step.title,
        content: step.content,
        disableBeacon: true,
      })) ?? [],
    [tour],
  );

  if (!canRun || !tour || steps.length === 0) return null;

  return (
    <TourContext.Provider value={{ requestSkip: () => setSkipConfirmationOpen(true) }}>
      <Joyride
        continuous
        run={running}
        steps={steps}
        stepIndex={stepIndex}
        onEvent={handleEvent}
        tooltipComponent={TourTooltip}
        scrollToFirstStep
        options={{
          buttons: ["back", "skip", "primary"],
          disableFocusTrap: false,
          dismissKeyAction: false,
          overlayClickAction: false,
          spotlightPadding: 8,
          targetWaitTimeout: 2500,
          scrollDuration: reducedMotion ? 0 : 400,
          zIndex: 1000,
        }}
      />
      <AlertDialog
        open={skipConfirmationOpen}
        onOpenChange={setSkipConfirmationOpen}
      >
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>{t("frontend.help.tour_skip_title")}</AlertDialogTitle>
            <AlertDialogDescription>
              {t("frontend.help.tour_skip_description")}
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel disabled={acknowledging}>
              {t("frontend.help.tour_keep_going")}
            </AlertDialogCancel>
            <AlertDialogAction
              disabled={acknowledging}
              onClick={() => void acknowledge("skipped")}
            >
              {t("frontend.help.tour_confirm_skip")}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </TourContext.Provider>
  );
}
