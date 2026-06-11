import { useState } from "react";
import { ChevronLeft, ChevronRight, LogOut, Menu } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Sheet, SheetContent, SheetTrigger } from "@/components/ui/sheet";
import { cn } from "@/lib/utils";
import { NavItem } from "./sidebar-nav";

export interface SidebarItem {
  label: string
  icon: React.ReactNode
  active?: boolean
  onSelect: () => void
}

interface SidebarContentProps {
  brandName: string
  collapsedBrandName: string
  username: string
  items: SidebarItem[]
  collapsed?: boolean
  onToggleCollapse?: () => void
  onLogout: () => void
  onCloseMobile?: () => void
}

function SidebarContent({
  brandName,
  collapsedBrandName,
  username,
  items,
  collapsed,
  onToggleCollapse,
  onLogout,
  onCloseMobile,
}: SidebarContentProps) {
  function handleSelect(item: SidebarItem) {
    item.onSelect();
    onCloseMobile?.();
  }

  function handleLogout() {
    onLogout();
    onCloseMobile?.();
  }

  return (
    <div className="flex h-full flex-col">
      <div className="h-14 flex items-center px-4 border-b shrink-0">
        <span
          className={cn(
            "font-bold tracking-tight text-primary transition-all",
            collapsed ? "text-lg" : "text-xl"
          )}
        >
          {collapsed ? collapsedBrandName : brandName}
        </span>
      </div>

      <nav className="flex-1 p-2 flex flex-col gap-1">
        {items.map((item) => (
          <NavItem
            key={item.label}
            icon={item.icon}
            label={item.label}
            collapsed={collapsed}
            active={item.active}
            onClick={() => handleSelect(item)}
          />
        ))}
      </nav>

      <div className="p-2 border-t flex flex-col gap-1">
        {onToggleCollapse && (
          <NavItem
            icon={
              collapsed ? (
                <ChevronRight className="size-4 shrink-0" />
              ) : (
                <ChevronLeft className="size-4 shrink-0" />
              )
            }
            label="Collapse"
            collapsed={collapsed}
            onClick={onToggleCollapse}
          />
        )}

        {!collapsed && (
          <div className="px-3 py-2">
            <span className="text-sm text-muted-foreground truncate block">
              {username}
            </span>
          </div>
        )}

        <NavItem
          icon={<LogOut className="size-4 shrink-0" />}
          label="Logout"
          collapsed={collapsed}
          onClick={handleLogout}
        />
      </div>
    </div>
  );
}

interface AppSidebarProps {
  brandName?: string
  collapsedBrandName?: string
  username: string
  items: SidebarItem[]
  onLogout: () => void
}

export function AppSidebar({
  brandName = "TrackPal",
  collapsedBrandName = "TP",
  username,
  items,
  onLogout,
}: AppSidebarProps) {
  const [collapsed, setCollapsed] = useState(false);

  return (
    <aside
      className={cn(
        "hidden md:flex flex-col border-r bg-card transition-all duration-200 shrink-0",
        collapsed ? "w-[60px]" : "w-[220px]"
      )}
    >
      <SidebarContent
        brandName={brandName}
        collapsedBrandName={collapsedBrandName}
        username={username}
        items={items}
        collapsed={collapsed}
        onToggleCollapse={() => setCollapsed((c) => !c)}
        onLogout={onLogout}
      />
    </aside>
  );
}

export function MobileSidebar({
  brandName = "TrackPal",
  collapsedBrandName = "TP",
  username,
  items,
  onLogout,
}: AppSidebarProps) {
  const [open, setOpen] = useState(false);

  return (
    <div className="md:hidden flex items-center gap-3 h-14 px-4 border-b">
      <Sheet open={open} onOpenChange={setOpen}>
        <SheetTrigger asChild>
          <Button variant="ghost" size="icon" className="shrink-0">
            <Menu className="size-5" />
            <span className="sr-only">Toggle menu</span>
          </Button>
        </SheetTrigger>
        <SheetContent side="left" className="w-[240px] p-0">
          <SidebarContent
            brandName={brandName}
            collapsedBrandName={collapsedBrandName}
            username={username}
            items={items}
            onLogout={onLogout}
            onCloseMobile={() => setOpen(false)}
          />
        </SheetContent>
      </Sheet>
      <span className="font-bold tracking-tight text-primary">{brandName}</span>
    </div>
  );
}
