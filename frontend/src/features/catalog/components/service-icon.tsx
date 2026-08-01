import { useEffect, useState } from "react";
import { Icon, loadIcon, type IconifyIcon } from "@iconify/react";
import { Package } from "lucide-react";

interface ServiceIconProps {
  icon: string | null | undefined;
  label: string;
  className?: string;
}

export function ServiceIcon({
  icon,
  label,
  className,
}: ServiceIconProps): React.ReactElement {
  const [data, setData] = useState<Required<IconifyIcon> | null>(null);
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    if (!icon) {
      setData(null);
      setFailed(false);
      return;
    }

    // Reset state immediately when icon changes so stale data is not shown
    setData(null);
    setFailed(false);

    let cancelled = false;

    loadIcon(icon)
      .then((loaded) => {
        if (!cancelled) setData(loaded);
      })
      .catch(() => {
        if (!cancelled) setFailed(true);
      });

    return () => {
      cancelled = true;
    };
  }, [icon]);

  if (failed || !data) {
    return (
      <span role="img" aria-label={label}>
        <Package data-testid="service-icon-fallback" aria-hidden="true" className={className} />
      </span>
    );
  }

  return (
    <span role="img" aria-label={label}>
      <Icon aria-hidden="true" icon={data} className={className} />
    </span>
  );
}
