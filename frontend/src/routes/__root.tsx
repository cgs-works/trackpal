import { createRootRoute, Outlet } from "@tanstack/react-router";
import { TanStackRouterDevtools } from "@tanstack/router-devtools";
import { useEffect, useState } from "react";
import { Toaster } from "@/components/ui/sonner";
import { isCatalogReady } from "@/i18n";
import { readBrowserStorage } from "@/lib/browser-storage";
import { loadCatalogForDataSource, useAuthStore } from "@/store/auth";

function RootComponent() {
  const [catalogLoaded, setCatalogLoaded] = useState(isCatalogReady());

  // Initialize theme from localStorage before first paint
  useEffect(() => {
    const stored = readBrowserStorage("theme");
    const shouldBeDark = stored ? stored === "dark" : true;
    document.documentElement.classList.toggle("dark", shouldBeDark);
  }, []);

  // Load i18n catalog if authenticated, block rendering until done
  useEffect(() => {
    const token = readBrowserStorage("token");
    if (!token || isCatalogReady()) {
      setCatalogLoaded(true);
      return;
    }
    loadCatalogForDataSource(useAuthStore.getState().dataSource).then(() =>
      setCatalogLoaded(true),
    );
  }, []);

  // Don't render children until catalog is loaded (prevents raw key flash)
  if (!catalogLoaded) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-background">
        <div className="h-5 w-5 animate-spin rounded-full border-2 border-muted-foreground border-t-transparent" />
      </div>
    );
  }

  return (
    <div className="min-h-screen flex flex-col bg-background text-foreground antialiased font-sans">
      <Outlet />
      <Toaster richColors position="top-right" />
      {import.meta.env.DEV && (
        <TanStackRouterDevtools position="bottom-right" />
      )}
    </div>
  );
}

export const Route = createRootRoute({
  component: RootComponent,
});
