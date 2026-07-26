import { useCallback, useEffect, useRef, useState } from "react";
import { useAuthStore } from "@/store/auth";

const HEARTBEAT_INTERVAL_MS = 60_000;
const CONSECUTIVE_FAILURES_BEFORE_PAUSE = 2;

export interface DemoHeartbeatState {
  consecutiveFailures: number;
  isPaused: boolean;
}

export function useDemoHeartbeat(): DemoHeartbeatState {
  const [consecutiveFailures, setConsecutiveFailures] = useState(0);
  const heartbeat = useAuthStore((s) => s.heartbeat);
  const demo = useAuthStore((s) => s.demo);
  const isActive = useRef(true);

  const runHeartbeat = useCallback(async () => {
    if (!isActive.current) return;
    try {
      await heartbeat();
      setConsecutiveFailures(0);
    } catch {
      if (!isActive.current) return;
      setConsecutiveFailures((prev) => prev + 1);
    }
  }, [heartbeat]);

  useEffect(() => {
    if (!demo) return;

    isActive.current = true;
    setConsecutiveFailures(0);

    // Immediate heartbeat on mount
    void runHeartbeat();

    const intervalId = window.setInterval(runHeartbeat, HEARTBEAT_INTERVAL_MS);

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
      isActive.current = false;
      window.clearInterval(intervalId);
      window.removeEventListener("focus", handleFocus);
      document.removeEventListener("visibilitychange", handleVisibilityChange);
    };
  }, [demo, runHeartbeat]);

  return {
    consecutiveFailures,
    isPaused: consecutiveFailures >= CONSECUTIVE_FAILURES_BEFORE_PAUSE,
  };
}
