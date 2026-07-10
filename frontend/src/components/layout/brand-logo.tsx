import { cn } from "@/lib/utils";

interface BrandLogoProps {
  compact?: boolean
  className?: string
}

export function BrandLogo({ compact = false, className }: BrandLogoProps) {
  if (compact) {
    return (
      <span
        role="img"
        aria-label="TrackPal"
        className={cn("font-heading text-sm font-semibold text-primary", className)}
      >
        TP
      </span>
    );
  }

  return (
    <span role="img" aria-label="TrackPal" className={cn("relative block h-7 w-[126px]", className)}>
      <img
        src="/trackpal-dark.png"
        alt=""
        aria-hidden="true"
        className="absolute inset-0 hidden h-full w-full object-contain object-left dark:block"
      />
      <img
        src="/trackpal-light.png"
        alt=""
        aria-hidden="true"
        className="absolute inset-0 h-full w-full object-contain object-left dark:hidden"
      />
    </span>
  );
}
