import { createRootRoute, Outlet } from "@tanstack/react-router";
import { TanStackRouterDevtools } from "@tanstack/router-devtools";
import { useEffect } from "react";
import { Toaster } from "@/components/ui/sonner";

function RootComponent() {
  // Initialize theme from localStorage before first paint
  useEffect(() => {
    const stored = localStorage.getItem("theme");
    const shouldBeDark = stored ? stored === "dark" : true;
    document.documentElement.classList.toggle("dark", shouldBeDark);
  }, []);

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
