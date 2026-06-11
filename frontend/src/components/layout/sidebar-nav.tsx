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
        "flex items-center gap-3 px-3 py-2 rounded-md text-sm font-medium transition-colors w-full text-left",
        active
          ? "bg-accent text-accent-foreground"
          : "text-muted-foreground hover:bg-accent hover:text-accent-foreground"
      )}
    >
      {icon}
      {!collapsed && <span>{label}</span>}
    </button>
  );
}
