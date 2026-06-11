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
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";

export const Route = createFileRoute("/login")({
  component: LoginComponent,
});

function LoginComponent() {
  const navigate = useNavigate();
  const { login } = useAuthStore();

  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [errorMessage, setErrorMessage] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [, setTick] = useState(0);

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
    <div className="flex-1 flex items-center justify-center p-4 bg-muted/30">
      <Card className="w-full max-w-sm shadow-md border">
        <CardHeader className="space-y-1">
          <CardTitle className="text-2xl font-bold text-center">
            {t("login.title")}
          </CardTitle>
          <CardDescription className="text-center">
            TrackPal
          </CardDescription>
        </CardHeader>
        <form onSubmit={handleSubmit}>
          <CardContent className="space-y-4">
            {/* Locale selector */}
            <div className="flex items-center justify-end gap-2">
              <Label htmlFor="locale-select" className="text-xs text-muted-foreground">
                {t("login.language")}:
              </Label>
              <select
                id="locale-select"
                value={getLocale()}
                onChange={(e) =>
                  setLocale(e.target.value as "en" | "es")
                }
                className="text-xs border border-input rounded-md bg-background px-2 py-1 focus:outline-none focus:ring-2 focus:ring-ring"
              >
                <option value="en">English</option>
                <option value="es">Español</option>
              </select>
            </div>

            {/* Username */}
            <div className="space-y-2">
              <Label htmlFor="username">{t("login.username")}</Label>
              <Input
                id="username"
                type="text"
                autoComplete="username"
                required
                value={username}
                onChange={(e) => setUsername(e.target.value)}
              />
            </div>

            {/* Password */}
            <div className="space-y-2">
              <Label htmlFor="password">{t("login.password")}</Label>
              <Input
                id="password"
                type="password"
                autoComplete="current-password"
                required
                value={password}
                onChange={(e) => setPassword(e.target.value)}
              />
            </div>

            {/* Error */}
            {errorMessage && (
              <p className="text-sm font-medium text-destructive" role="alert">
                {errorMessage}
              </p>
            )}
          </CardContent>

          <div className="px-6 pb-6">
            <Button
              className="w-full"
              type="submit"
              disabled={isLoading}
            >
              {isLoading ? t("login.signing_in") : t("login.sign_in")}
            </Button>
          </div>
        </form>
      </Card>
    </div>
  );
}
