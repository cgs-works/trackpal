import { useCallback, useEffect, useRef, useState } from "react";
import { getWhatsAppLinkStatus } from "@/features/admin/services/whatsapp-link-api";
import type { WhatsAppLinkStatus } from "@/features/admin/services/whatsapp-link-api";

export interface UseWhatsAppLinkPollingOptions {
  enabled: boolean;
  intervalMs?: number;
  timeoutMs?: number;
  onStatus?: (status: WhatsAppLinkStatus) => void;
  onConnected: (status: WhatsAppLinkStatus) => void;
  onTimeout: () => void;
  onError?: (error: unknown) => void;
}

export function useWhatsAppLinkPolling(
  options: UseWhatsAppLinkPollingOptions,
): { isPolling: boolean; elapsedMs: number; stop: () => void } {
  const {
    enabled,
    intervalMs = 5000,
    timeoutMs = 60000,
    onStatus,
    onConnected,
    onTimeout,
    onError,
  } = options;

  const [isPolling, setIsPolling] = useState(false);
  const [elapsedMs, setElapsedMs] = useState(0);

  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const timeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const elapsedRef = useRef(0);
  const mountedRef = useRef(true);
  const calledConnectedRef = useRef(false);
  const stoppedRef = useRef(false);

  const clearTimers = useCallback(() => {
    if (intervalRef.current !== null) {
      clearInterval(intervalRef.current);
      intervalRef.current = null;
    }
    if (timeoutRef.current !== null) {
      clearTimeout(timeoutRef.current);
      timeoutRef.current = null;
    }
  }, []);

  const stop = useCallback(() => {
    stoppedRef.current = true;
    clearTimers();
    setIsPolling(false);
  }, [clearTimers]);

  useEffect(() => {
    mountedRef.current = true;
    return () => {
      mountedRef.current = false;
      clearTimers();
    };
  }, [clearTimers]);

  useEffect(() => {
    if (!enabled) {
      stop();
      return;
    }

    stoppedRef.current = false;
    calledConnectedRef.current = false;
    elapsedRef.current = 0;
    setElapsedMs(0);
    setIsPolling(true);

    const poll = async () => {
      if (stoppedRef.current || !mountedRef.current) return;

      try {
        const status = await getWhatsAppLinkStatus();
        if (stoppedRef.current || !mountedRef.current) return;

        onStatus?.(status);

        if (status.connected && !calledConnectedRef.current) {
          calledConnectedRef.current = true;
          onConnected(status);
          stop();
          return;
        }
      } catch (error) {
        if (stoppedRef.current || !mountedRef.current) return;
        onError?.(error);
      }
    };

    // Poll immediately
    poll();

    // Set up interval
    intervalRef.current = setInterval(() => {
      elapsedRef.current += intervalMs;
      setElapsedMs(elapsedRef.current);
      poll();
    }, intervalMs);

    // Set up timeout
    timeoutRef.current = setTimeout(() => {
      if (!stoppedRef.current && mountedRef.current) {
        clearTimers();
        setIsPolling(false);
        onTimeout();
      }
    }, timeoutMs);

    return () => {
      clearTimers();
    };
  }, [enabled]); // eslint-disable-line react-hooks/exhaustive-deps

  return { isPolling, elapsedMs, stop };
}
