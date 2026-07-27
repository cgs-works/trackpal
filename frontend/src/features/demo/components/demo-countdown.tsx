import { t } from "@/i18n";
import { useCountdown } from "@/features/demo/hooks/use-countdown";

export function DemoCountdown({ expiresAt, serverTime }: { expiresAt: string; serverTime: string }) {
  const remaining = useCountdown(expiresAt, serverTime);

  if (remaining <= 0) {
    return <span data-testid="demo-countdown-expired">{t("frontend.demo.banner.expired")}</span>;
  }

  const hours = Math.floor(remaining / 3600);
  const minutes = Math.floor((remaining % 3600) / 60);
  const parts: string[] = [];
  if (hours > 0) parts.push(t("frontend.master.demos.hours", { hours }));
  if (minutes > 0 || hours === 0) parts.push(t("frontend.master.demos.minutes", { minutes }));

  return (
    <span data-testid="demo-countdown" aria-live="off">
      {t("frontend.demo.banner.remaining", { time: parts.join(" ") })}
    </span>
  );
}
