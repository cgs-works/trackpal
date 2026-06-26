import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";

export function SupportBanner() {
  return (
    <Alert className="m-4 mb-0">
      <AlertTitle className="flex items-center gap-2">
        Support mode <Badge variant="secondary">Starter tenant</Badge>
      </AlertTitle>
      <AlertDescription>
        You are viewing the full Pro admin surface as Master support. Starter tenant admins cannot see these Pro-only modules.
      </AlertDescription>
    </Alert>
  );
}
