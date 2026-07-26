import { useEffect, useState } from "react";

function diffSeconds(expiresAt: string, serverTime: string): number {
  const exp = new Date(expiresAt).getTime();
  const now = new Date(serverTime).getTime();
  return Math.max(0, Math.floor((exp - now) / 1000));
}

export function useCountdown(
  expiresAt: string | null,
  serverTime: string | null,
): number {
  const [remaining, setRemaining] = useState<number>(() =>
    expiresAt && serverTime ? diffSeconds(expiresAt, serverTime) : 0,
  );

  useEffect(() => {
    if (!expiresAt || !serverTime) {
      setRemaining(0);
      return;
    }

    setRemaining(diffSeconds(expiresAt, serverTime));

    const id = window.setInterval(() => {
      setRemaining((prev) => Math.max(0, prev - 1));
    }, 1000);

    return () => window.clearInterval(id);
  }, [expiresAt, serverTime]);

  return remaining;
}
