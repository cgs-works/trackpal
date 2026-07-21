import { Link, type ToPathOption } from "@tanstack/react-router";
import { cn } from "@/lib/utils";

interface NavItemProps {
  icon: React.ReactNode
  label: string
  collapsed?: boolean
  active?: boolean
  to?: ToPathOption
  onClick?: () => void
}

export function NavItem({
  icon,
  label,
  collapsed,
  active,
  to,
  onClick,
}: NavItemProps) {
  const className = cn(
    "flex min-h-10 w-full items-center gap-3 rounded-lg px-3 py-2 text-left text-sm font-medium transition-colors duration-200",
    active
      ? "bg-sidebar-primary text-sidebar-primary-foreground shadow-[0_0_22px_-12px_var(--sidebar-primary)]"
      : "text-muted-foreground hover:bg-sidebar-accent hover:text-sidebar-accent-foreground"
  );
  const content = (
    <>
      {icon}
      {!collapsed && <span>{label}</span>}
    </>
  );

  if (to) {
    return (
      <Link
        to={to}
        aria-current={active ? "page" : undefined}
        className={className}
        onClick={onClick}
      >
        {content}
      </Link>
    );
  }

  return (
    <button
      type="button"
      onClick={onClick}
      aria-current={active ? "page" : undefined}
      className={className}
    >
      {content}
    </button>
  );
}
