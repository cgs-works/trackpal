import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
} from "react";
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
const TARGET_WAIT_TIMEOUT_MS = 2500;

export function requestHelpTourReplay() {
  window.dispatchEvent(new Event(HELP_TOUR_REPLAY_EVENT));
}

type TourContextValue = {
  requestSkip: () => void;
  requestLearnMore: (topicId: string) => void;
};
const TourContext = createContext<TourContextValue | null>(null);

export function waitForTourTarget(
  target: string,
  timeoutMs = TARGET_WAIT_TIMEOUT_MS,
): Promise<boolean> {
  const selector = tourSelector(target);
  if (document.querySelector(selector)) return Promise.resolve(true);

  return new Promise((resolve) => {
    const deadline = Date.now() + timeoutMs;
    const check = () => {
      if (document.querySelector(selector)) {
        resolve(true);
        return;
      }
      if (Date.now() >= deadline) {
        resolve(false);
        return;
      }
      window.setTimeout(check, 25);
    };
    window.setTimeout(check, 0);
  });
}

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
      data-tour-layout={isMobile ? "mobile-sheet" : "desktop-popover"}
      data-reduced-motion={useReducedMotion() ? "true" : "false"}
      className={
        isMobile
          ? "z-[1000] max-w-lg rounded-t-xl border bg-popover p-5 text-popover-foreground shadow-xl"
          : "z-[1000] max-w-lg rounded-xl border bg-popover p-5 text-popover-foreground shadow-xl"
      }
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
          {typeof step.data?.topic_id === "string" && (
            <Button
              type="button"
              variant="link"
              size="sm"
              onClick={() => context?.requestLearnMore(step.data.topic_id)}
            >
              {t("frontend.help.tour_learn_more")}
            </Button>
          )}
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
  const [targetReady, setTargetReady] = useState(false);
  const [skipConfirmationOpen, setSkipConfirmationOpen] = useState(false);
  const [acknowledging, setAcknowledging] = useState(false);

  const canRun =
    isPrivateHelpEnabled() &&
    isAuthenticated &&
    role === "tenant" &&
    !isMasterSupportContext;

  const stopTour = useCallback(() => {
    setRunning(false);
    setTargetReady(false);
    setTour(null);
    setStepIndex(0);
  }, []);

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
        setTargetReady(false);
        setRunning(true);
      } catch {
        // Help is optional and must not make the product unavailable.
      }
    },
    [],
  );

  useEffect(() => {
    if (!canRun) {
      stopTour();
      return;
    }
    void loadTour(getUnseenHelpTour);
  }, [canRun, loadTour, stopTour]);

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
    if (!step) {
      stopTour();
      return;
    }
    const destination = resolveSafeHelpNavigation(
      { route: step.route, settings_category: step.settings_category },
      "tenant",
    );
    if (!destination) {
      stopTour();
      return;
    }

    let cancelled = false;
    setTargetReady(false);
    const prepareStep = async () => {
      try {
        if (destination.to === "/admin/settings") {
          await navigate({ to: destination.to, search: destination.search });
        } else {
          await navigate({ to: destination.to });
        }
      } catch {
        if (!cancelled) stopTour();
        return;
      }

      const found = await waitForTourTarget(step.target);
      if (cancelled) return;
      if (found) {
        setTargetReady(true);
        return;
      }
      if (step.conditional && stepIndex < tour.steps.length - 1) {
        setStepIndex((current) => current + 1);
        return;
      }
      stopTour();
    };

    void prepareStep();
    return () => {
      cancelled = true;
    };
  }, [navigate, running, stepIndex, stopTour, tour]);

  const requestSkip = useCallback(() => {
    setRunning(false);
    setTargetReady(false);
    setSkipConfirmationOpen(true);
  }, []);

  const requestLearnMore = useCallback(
    (topicId: string) => {
      setRunning(false);
      setTargetReady(false);
      void navigate({ to: "/admin/help", search: { topic: topicId } });
    },
    [navigate],
  );

  const keepTourGoing = useCallback(() => {
    setSkipConfirmationOpen(false);
    if (tour) {
      setTargetReady(true);
      setRunning(true);
    }
  }, [tour]);

  const acknowledge = useCallback(
    async (status: "completed" | "skipped") => {
      if (!tour || acknowledging) return;
      setAcknowledging(true);
      try {
        await acknowledgeHelpTour(tour.release_id, status);
        setRunning(false);
        setTargetReady(false);
        setTour(null);
        setSkipConfirmationOpen(false);
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
        setTargetReady(false);
        setStepIndex(Math.max(0, nextIndex));
      }
      if (data.type === EVENTS.ERROR) {
        stopTour();
      }
      if (data.status === STATUS.FINISHED) {
        void acknowledge("completed");
      }
      if (data.status === STATUS.SKIPPED) {
        requestSkip();
      }
    },
    [acknowledge, requestSkip, stopTour],
  );

  const steps = useMemo<Step[]>(
    () =>
      tour?.steps.map((step) => ({
        target: tourSelector(step.target),
        title: step.title,
        content: step.content,
        data: { topic_id: step.topic_id },
        disableBeacon: true,
      })) ?? [],
    [tour],
  );

  if (!canRun || !tour || steps.length === 0) return null;

  return (
    <TourContext.Provider value={{ requestSkip, requestLearnMore }}>
      <Joyride
        continuous
        run={running && targetReady}
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
        styles={{
          spotlight: reducedMotion ? { className: "transition-none" } : undefined,
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
            <AlertDialogCancel
              disabled={acknowledging}
              onClick={keepTourGoing}
            >
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
