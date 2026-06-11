import { createFileRoute } from "@tanstack/react-router";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Package } from "lucide-react";

function CatalogPage() {
  return (
    <div className="flex-1 p-6">
      <div className="max-w-4xl mx-auto space-y-6">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">Catalog</h1>
          <p className="text-muted-foreground">
            Manage your services, plans, and pricing
          </p>
        </div>
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Package className="size-5" />
              Coming Soon
            </CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-muted-foreground">
              Catalog management will be migrated from the legacy Vue frontend.
            </p>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}

export const Route = createFileRoute("/admin/catalog")({
  component: CatalogPage,
});
