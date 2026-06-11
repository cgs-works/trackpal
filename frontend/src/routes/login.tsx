import { createFileRoute, useNavigate } from "@tanstack/react-router";
import { useState, useEffect } from "react";
import { useAuthStore } from "@/store/auth";
import {
  getLocale,
  setLocale,
  subscribeLocale,
  t,
} from "@/i18n/public";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Sun, Moon, Globe } from "lucide-react";

export const Route = createFileRoute("/login")({
  component: LoginComponent,
});

/* ── Atmospheric Panel ─────────────────────────────────────────── */

function AtmosphericPanel() {
  return (
    <div className="relative hidden md:flex flex-1 items-center justify-center overflow-hidden bg-[oklch(0.11_0_0)]">
      {/* Grid overlay */}
      <div
        className="absolute inset-0 opacity-[0.07]"
        style={{
          backgroundImage:
            "linear-gradient(rgba(255,255,255,0.5) 1px, transparent 1px), linear-gradient(90deg, rgba(255,255,255,0.5) 1px, transparent 1px)",
          backgroundSize: "60px 60px",
        }}
      />

      {/* Radial glow */}
      <div
        className="absolute inset-0"
        style={{
          background:
            "radial-gradient(ellipse 50% 50% at 50% 50%, oklch(0.55_0.12_260 / 0.15), transparent 70%)",
        }}
      />

      {/* Secondary glow — lower */}
      <div
        className="absolute inset-0 opacity-60"
        style={{
          background:
            "radial-gradient(ellipse 40% 30% at 50% 70%, oklch(0.50_0.08_300 / 0.12), transparent 60%)",
        }}
      />

      {/* Brand content */}
      <div className="relative z-10 flex flex-col items-center gap-6 px-8 text-center">
        {/* Accent line */}
        <div className="h-px w-16 bg-gradient-to-r from-transparent via-[oklch(0.7_0.1_260)] to-transparent opacity-40" />

        <h1 className="text-4xl font-extrabold tracking-tight text-white">
          TrackPal
        </h1>

        <p className="max-w-xs text-sm leading-relaxed text-white/40">
          Operations platform for WhatsApp-based service delivery and subscription management.
        </p>

        {/* Decorative dots */}
        <div className="flex gap-2 mt-4">
          {[0.3, 0.5, 0.3].map((opacity, i) => (
            <div
              key={i}
              className="h-1 rounded-full bg-white"
              style={{ opacity, width: i === 1 ? 24 : 8 }}
            />
          ))}
        </div>
      </div>
    </div>
  );
}

/* ── Theme Toggle ──────────────────────────────────────────────── */

function ThemeToggle({
  isDark,
  onToggle,
}: {
  isDark: boolean;
  onToggle: () => void;
}) {
  return (
    <button
      type="button"
      onClick={onToggle}
      className="inline-flex h-8 w-8 items-center justify-center rounded-lg text-muted-foreground transition-colors hover:text-foreground hover:bg-muted"
      aria-label={isDark ? "Switch to light mode" : "Switch to dark mode"}
    >
      {isDark ? <Sun className="h-4 w-4" /> : <Moon className="h-4 w-4" />}
    </button>
  );
}

/* ── Login ─────────────────────────────────────────────────────── */

function LoginComponent() {
  const navigate = useNavigate();
  const { login } = useAuthStore();

  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [errorMessage, setErrorMessage] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [, setTick] = useState(0);

  // Theme state — default dark
  const [isDark, setIsDark] = useState(() => {
    if (typeof window === "undefined") return true;
    const stored = localStorage.getItem("theme");
    if (stored) return stored === "dark";
    return true; // default dark
  });

  // Sync theme to <html> class + localStorage
  useEffect(() => {
    const root = document.documentElement;
    if (isDark) {
      root.classList.add("dark");
    } else {
      root.classList.remove("dark");
    }
    localStorage.setItem("theme", isDark ? "dark" : "light");
  }, [isDark]);

  useEffect(() => subscribeLocale(() => setTick((n) => n + 1)), []);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setErrorMessage("");
    setIsLoading(true);

    try {
      const data = await login(username, password);
      const role = data.user?.role;

      if (role === "master") {
        await navigate({ to: "/master/dashboard" });
      } else if (role === "tenant") {
        await navigate({ to: "/admin/dashboard" });
      } else if (role === "client") {
        await navigate({ to: "/client/dashboard" });
      } else {
        setErrorMessage(t("login.unknown_role"));
      }
    } catch (error: unknown) {
      const apiErr = error as {
        response?: { data?: { detail?: string } };
      };
      setErrorMessage(
        apiErr.response?.data?.detail || t("login.error")
      );
    } finally {
      setIsLoading(false);
    }
  }

  return (
    <div className="flex h-screen bg-background text-foreground">
      {/* Left: atmospheric panel */}
      <AtmosphericPanel />

      {/* Right: form panel */}
      <div className="flex w-full items-center justify-center p-6 sm:p-10 md:w-[480px] lg:w-[520px]">
        <div className="w-full max-w-sm space-y-8">
          {/* Mobile brand header */}
          <div className="flex flex-col items-center gap-2 md:hidden">
            <h1 className="text-2xl font-bold tracking-tight">TrackPal</h1>
            <p className="text-xs text-muted-foreground">
              Operations platform
            </p>
          </div>

          {/* Header row: heading + controls */}
          <div className="flex items-start justify-between">
            <div>
              <h2 className="text-xl font-semibold tracking-tight">
                {t("login.title")}
              </h2>
              <p className="mt-1 text-sm text-muted-foreground">
                {t("login.welcome")}
              </p>
            </div>

            <div className="flex items-center gap-1">
              <ThemeToggle
                isDark={isDark}
                onToggle={() => setIsDark((d) => !d)}
              />
            </div>
          </div>

          <form onSubmit={handleSubmit} className="space-y-5">
            {/* Locale selector */}
            <div className="flex items-center gap-2">
              <Globe className="h-3.5 w-3.5 text-muted-foreground" />
              <select
                value={getLocale()}
                onChange={(e) => setLocale(e.target.value as "en" | "es")}
                className="h-8 rounded-lg border border-input bg-transparent px-2 text-xs text-foreground focus:outline-none focus:ring-2 focus:ring-ring"
              >
                <option value="en">English</option>
                <option value="es">Español</option>
              </select>
            </div>

            {/* Username */}
            <div className="space-y-2">
              <Label htmlFor="username" className="text-sm font-medium">
                {t("login.username")}
              </Label>
              <Input
                id="username"
                type="text"
                autoComplete="username"
                required
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                className="h-10 transition-[box-shadow] duration-200 focus-visible:ring-[oklch(0.65_0.15_260/0.4)] focus-visible:border-[oklch(0.65_0.15_260)]"
              />
            </div>

            {/* Password */}
            <div className="space-y-2">
              <Label htmlFor="password" className="text-sm font-medium">
                {t("login.password")}
              </Label>
              <Input
                id="password"
                type="password"
                autoComplete="current-password"
                required
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                className="h-10 transition-[box-shadow] duration-200 focus-visible:ring-[oklch(0.65_0.15_260/0.4)] focus-visible:border-[oklch(0.65_0.15_260)]"
              />
            </div>

            {/* Error */}
            {errorMessage && (
              <p className="text-sm font-medium text-destructive" role="alert">
                {errorMessage}
              </p>
            )}

            {/* Submit */}
            <Button
              className="w-full h-10"
              type="submit"
              disabled={isLoading}
            >
              {isLoading ? t("login.signing_in") : t("login.sign_in")}
            </Button>
          </form>
        </div>
      </div>
    </div>
  );
}
