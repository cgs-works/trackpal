import { Link } from "@tanstack/react-router";
import { buttonVariants } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { t } from "@/i18n";

export function NotFoundPage() {
  return (
    <div className="flex min-h-[60vh] items-center justify-center p-6">
      <Card className="w-full max-w-md">
        <CardHeader>
          <CardTitle>404</CardTitle>
        </CardHeader>
        <CardContent className="flex flex-col gap-4">
          <p className="text-sm text-muted-foreground">{t("frontend.not_found.description")}</p>
          <Link to="/admin/dashboard" className={buttonVariants()}>
            {t("frontend.not_found.go_dashboard")}
          </Link>
        </CardContent>
      </Card>
    </div>
  );
}
