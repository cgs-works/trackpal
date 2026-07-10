import { cn } from "@/lib/utils";

interface NavItemProps {
  icon: React.ReactNode
  label: string
  collapsed?: boolean
  active?: boolean
  onClick?: () => void
}

export function NavItem({
  icon,
  label,
  collapsed,
  active,
  onClick,
}: NavItemProps) {
  return (
    <button
      onClick={onClick}
      className={cn(
        "flex min-h-10 w-full items-center gap-3 rounded-lg px-3 py-2 text-left text-sm font-medium transition-colors duration-200",
        active
          ? "bg-sidebar-primary text-sidebar-primary-foreground shadow-[0_0_22px_-12px_var(--sidebar-primary)]"
          : "text-muted-foreground hover:bg-sidebar-accent hover:text-sidebar-accent-foreground"
      )}
    >
      {icon}
      {!collapsed && <span>{label}</span>}
    </button>
  );
}
