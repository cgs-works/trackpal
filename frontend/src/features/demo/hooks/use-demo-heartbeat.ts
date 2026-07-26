import { useCallback, useEffect, useRef, useState } from "react";
import { useAuthStore } from "@/store/auth";

const HEARTBEAT_INTERVAL_MS = 60_000;
const CONSECUTIVE_FAILURES_BEFORE_PAUSE = 2;

export interface DemoHeartbeatState {
  consecutiveFailures: number;
  isPaused: boolean;
  retry: () => void;
}

export function useDemoHeartbeat(): DemoHeartbeatState {
  const [consecutiveFailures, setConsecutiveFailures] = useState(0);
  const heartbeat = useAuthStore((s) => s.heartbeat);
  const demoTenantId = useAuthStore((s) => s.demo?.tenantId ?? null);
  const demoStatus = useAuthStore((s) => s.demo?.status ?? null);
  const isAuthenticated = useAuthStore((s) => s.isAuthenticated);
  const isActive = useRef(false);
  const generation = useRef(0);
  const inFlight = useRef<Promise<void> | null>(null);

  const runHeartbeat = useCallback(async () => {
    if (
      !isActive.current ||
      !demoTenantId ||
      demoStatus !== "active" ||
      !isAuthenticated
    ) {
      return;
    }
    if (inFlight.current) return inFlight.current;

    const requestGeneration = generation.current;
    const request = (async () => {
      try {
        await heartbeat();
        if (!isActive.current || requestGeneration !== generation.current) return;
        setConsecutiveFailures(0);
      } catch {
        if (!isActive.current || requestGeneration !== generation.current) return;
        setConsecutiveFailures((previous) => previous + 1);
      } finally {
        if (requestGeneration === generation.current) {
          inFlight.current = null;
        }
      }
    })();

    inFlight.current = request;
    return request;
  }, [demoStatus, demoTenantId, heartbeat, isAuthenticated]);

  const retry = useCallback(() => {
    void runHeartbeat();
  }, [runHeartbeat]);

  useEffect(() => {
    generation.current += 1;
    inFlight.current = null;
    isActive.current = Boolean(
      demoTenantId && demoStatus === "active" && isAuthenticated,
    );
    setConsecutiveFailures(0);

    if (!isActive.current) {
      return () => {
        generation.current += 1;
        isActive.current = false;
        inFlight.current = null;
      };
    }

    void runHeartbeat();
    const intervalId = window.setInterval(() => {
      void runHeartbeat();
    }, HEARTBEAT_INTERVAL_MS);

    const handleFocus = () => {
      void runHeartbeat();
    };

    const handleVisibilityChange = () => {
      if (document.visibilityState === "visible") {
        void runHeartbeat();
      }
    };

    window.addEventListener("focus", handleFocus);
    document.addEventListener("visibilitychange", handleVisibilityChange);

    return () => {
      generation.current += 1;
      isActive.current = false;
      inFlight.current = null;
      window.clearInterval(intervalId);
      window.removeEventListener("focus", handleFocus);
      document.removeEventListener("visibilitychange", handleVisibilityChange);
    };
  }, [demoStatus, demoTenantId, isAuthenticated, runHeartbeat]);

  return {
    consecutiveFailures,
    isPaused: consecutiveFailures >= CONSECUTIVE_FAILURES_BEFORE_PAUSE,
    retry,
  };
}
