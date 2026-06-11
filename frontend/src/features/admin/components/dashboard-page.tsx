import { useAuthStore } from "@/store/auth";
import { Navigate } from "@tanstack/react-router";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Settings, LogOut } from "lucide-react";

export function DashboardPage() {
  const { isAuthenticated, role, username, logout } = useAuthStore();

  if (!isAuthenticated || role !== "tenant") {
    return <Navigate to="/login" replace />;
  }

  return (
    <div className="flex-1 p-6">
      <div className="max-w-4xl mx-auto flex flex-col gap-6">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-bold tracking-tight">Tenant Dashboard</h1>
            <p className="text-muted-foreground">
              Welcome back, {username || "Admin"}
            </p>
          </div>
          <Button variant="outline" size="sm" onClick={() => logout()}>
            <LogOut className="size-4 mr-2" />
            Logout
          </Button>
        </div>

        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Settings className="size-5" />
              Coming Soon
            </CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-muted-foreground">
              Tenant management features will be migrated from the legacy Vue frontend.
            </p>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
