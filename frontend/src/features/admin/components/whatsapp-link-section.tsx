import { useCallback, useEffect, useRef, useState } from "react";
import { ExternalLink, Loader2, MessageCircle, QrCode, Smartphone } from "lucide-react";
import { toast } from "sonner";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { t } from "@/i18n";
import { useAuthStore } from "@/store/auth";
import { getApiError } from "@/lib/api-errors";
import {
  disconnectWhatsApp,
  getQRCode,
  getWhatsAppLinkStatus,
  requestPairingCode,
} from "../services/whatsapp-link-api";
import { useWhatsAppLinkPolling } from "../hooks/use-whatsapp-link-polling";
import type { WhatsAppLinkStatus } from "../services/whatsapp-link-api";

type BadgeState = "connected" | "disconnected" | "connecting";

function getQrImageSrc(qrcode: string): string {
  return qrcode.startsWith("data:") ? qrcode : `data:image/png;base64,${qrcode}`;
}

function StatusBadge({ state }: { state: BadgeState }) {
  const map: Record<BadgeState, { label: string; variant: "default" | "secondary" | "outline" }> = {
    connected: { label: t("frontend.whatsapp_link.status_connected"), variant: "default" },
    disconnected: { label: t("frontend.whatsapp_link.status_disconnected"), variant: "secondary" },
    connecting: { label: t("frontend.whatsapp_link.status_connecting"), variant: "outline" },
  };
  const { label, variant } = map[state];
  return <Badge variant={variant}>{label}</Badge>;
}

export function WhatsappLinkSection() {
  const [status, setStatus] = useState<WhatsAppLinkStatus | null>(null);
  const [isInitialLoading, setIsInitialLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [pairingCode, setPairingCode] = useState<string | null>(null);
  const [qrCode, setQrCode] = useState<string | null>(null);
  const [isRequestingPair, setIsRequestingPair] = useState(false);
  const [isRequestingQr, setIsRequestingQr] = useState(false);
  const [pairError, setPairError] = useState<string | null>(null);
  const [qrError, setQrError] = useState<string | null>(null);
  const [isDisconnecting, setIsDisconnecting] = useState(false);
  const [pollingEnabled, setPollingEnabled] = useState(false);
  const [timeoutError, setTimeoutError] = useState(false);
  const [disconnectDialogOpen, setDisconnectDialogOpen] = useState(false);
  const isDemo = useAuthStore((state) => state.dataSource.mode === "demo");
  const isStarterDemo = useAuthStore(
    (state) => isDemo && (state.demo?.plan ?? state.dataSource.context.tenantPlan) === "starter",
  );
  const qrRefreshTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  // Refs for stale closure prevention in QR refresh timer
  const pollingEnabledRef = useRef(pollingEnabled);
  const connectedRef = useRef(status?.connected === true);

  useEffect(() => {
    pollingEnabledRef.current = pollingEnabled;
  }, [pollingEnabled]);

  useEffect(() => {
    connectedRef.current = status?.connected === true;
  }, [status?.connected]);

  const connected = status?.connected === true;
  const hasPhone = !!status?.phone;
  const badgeState: BadgeState = pollingEnabled ? "connecting" : connected ? "connected" : "disconnected";

  // ---- Status loading ----

  const loadStatus = useCallback(async () => {
    try {
      setError(null);
      const data = isDemo
        ? { connected: true, phone: null, instance_name: "Demo WhatsApp" }
        : await getWhatsAppLinkStatus();
      setStatus(data);
    } catch (err) {
      setError(getApiError(err, t("frontend.whatsapp_link.error_load")));
    } finally {
      setIsInitialLoading(false);
    }
  }, [isDemo]);

  useEffect(() => {
    loadStatus();
  }, [loadStatus]);

  // ---- QR auto-refresh timer (defined before polling hook to avoid forward ref issues) ----

  const clearQrRefreshTimer = useCallback(() => {
    if (qrRefreshTimer.current !== null) {
      clearTimeout(qrRefreshTimer.current);
      qrRefreshTimer.current = null;
    }
  }, []);

  // Use a ref to avoid forward-reference lint errors
  const scheduleQrRefreshRef = useRef<() => void>(() => {});

  const scheduleQrRefresh = useCallback(() => {
    clearQrRefreshTimer();
    // Refresh QR approximately 5 seconds before the 40-second expiry window
    qrRefreshTimer.current = setTimeout(async () => {
      // Read live state from refs to avoid stale closure
      if (!pollingEnabledRef.current && !connectedRef.current) {
        try {
          const { qrcode } = await getQRCode();
          setQrCode(qrcode);
          scheduleQrRefreshRef.current(); // reschedule via ref
        } catch {
          // Silently fail; user can manually refresh
        }
      }
    }, 35000);
  }, [clearQrRefreshTimer]);

  useEffect(() => {
    scheduleQrRefreshRef.current = scheduleQrRefresh;
  }, [scheduleQrRefresh]);

  useEffect(() => {
    return () => {
      clearQrRefreshTimer();
    };
  }, [clearQrRefreshTimer]);

  // ---- Polling hook ----

  useWhatsAppLinkPolling({
    enabled: pollingEnabled,
    onConnected: (newStatus) => {
      setStatus(newStatus);
      setPollingEnabled(false);
      setPairingCode(null);
      setQrCode(null);
      setTimeoutError(false);
      clearQrRefreshTimer();
      toast.success(t("frontend.whatsapp_link.success_linked"));
    },
    onTimeout: () => {
      setPollingEnabled(false);
      setTimeoutError(true);
      clearQrRefreshTimer(); // Clear QR refresh on timeout
    },
  });

  // ---- Handlers ----

  const handleRequestPairingCode = async () => {
    setIsRequestingPair(true);
    setPairError(null);
    try {
      const { code } = await requestPairingCode();
      setPairingCode(code);
      setPollingEnabled(true);
      setTimeoutError(false);
    } catch (err) {
      setPairError(getApiError(err, t("frontend.whatsapp_link.error_pair")));
    } finally {
      setIsRequestingPair(false);
    }
  };

  const handleLoadQrCode = async () => {
    setIsRequestingQr(true);
    setQrError(null);
    try {
      const { qrcode } = await getQRCode();
      setQrCode(qrcode);
      setPollingEnabled(true);
      setTimeoutError(false);
      scheduleQrRefresh();
    } catch (err) {
      setQrError(getApiError(err, t("frontend.whatsapp_link.error_qr")));
    } finally {
      setIsRequestingQr(false);
    }
  };

  const handleDisconnectConfirm = async () => {
    setIsDisconnecting(true);
    try {
      await disconnectWhatsApp();
      setDisconnectDialogOpen(false);
      setPairingCode(null);
      setQrCode(null);
      setPollingEnabled(false);
      setTimeoutError(false);
      clearQrRefreshTimer();
      toast.success(t("frontend.whatsapp_link.success_disconnected"));
      await loadStatus();
    } catch (err) {
      setDisconnectDialogOpen(false); // Close dialog on failure so error is visible
      setError(getApiError(err, t("frontend.whatsapp_link.error_disconnect")));
    } finally {
      setIsDisconnecting(false);
    }
  };

  const handleRetry = () => {
    setIsInitialLoading(true); // Reset to show skeleton during reload
    setError(null);
    setPairError(null);
    setQrError(null);
    setTimeoutError(false);
    setPollingEnabled(false);
    setPairingCode(null);
    setQrCode(null);
    clearQrRefreshTimer();
    loadStatus();
  };

  // ---- Render: Loading ----

  if (isInitialLoading) {
    return (
      <div role="status" className="flex flex-col gap-4">
        <Skeleton className="h-5 w-48" />
        <Skeleton className="h-4 w-72" />
        <Skeleton className="h-10 w-full" />
      </div>
    );
  }

  // ---- Render: Error ----

  if (error && !status) {
    return (
      <Card>
        <CardContent className="flex flex-col items-center gap-4 py-6 text-center">
          <Alert variant="destructive">
            <AlertTitle>{t("frontend.whatsapp_link.error_load")}</AlertTitle>
            <AlertDescription>{error}</AlertDescription>
          </Alert>
          <Button variant="outline" onClick={handleRetry} aria-label={t("frontend.whatsapp_link.retry")}>
            {t("frontend.whatsapp_link.retry")}
          </Button>
        </CardContent>
      </Card>
    );
  }

  // ---- Render: Main ----

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <MessageCircle className="size-5" />
          {t("frontend.whatsapp_link.heading")}
        </CardTitle>
        <CardDescription>{t("frontend.whatsapp_link.description")}</CardDescription>
      </CardHeader>
      <CardContent className="flex flex-col gap-6">
        {/* Status summary */}
        <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between sm:gap-4">
          <div className="flex flex-col gap-1">
            <div className="flex items-center gap-2 text-sm">
              <Smartphone className="size-4 text-muted-foreground" />
              <span className="text-muted-foreground">{t("frontend.whatsapp_link.phone_label")}:</span>
              <span>{status?.phone ?? "—"}</span>
            </div>
            <div className="flex items-center gap-2 text-sm">
              <span className="text-muted-foreground">{t("frontend.whatsapp_link.instance_label")}:</span>
              <span>{status?.instance_name ?? "—"}</span>
            </div>
          </div>
          <StatusBadge state={badgeState} />
        </div>

        {/* Error display */}
        {error && (
          <Alert variant="destructive">
            <AlertTitle>{t("frontend.whatsapp_link.error_load")}</AlertTitle>
            <AlertDescription>{error}</AlertDescription>
          </Alert>
        )}

        {/* No phone alert */}
        {!hasPhone && !connected && (
          <Alert>
            <AlertTitle>{t("frontend.whatsapp_link.no_phone_title")}</AlertTitle>
            <AlertDescription>{t("frontend.whatsapp_link.no_phone_description")}</AlertDescription>
          </Alert>
        )}

        {connected && isStarterDemo && (
          <div className="flex flex-col gap-3 rounded-lg border bg-muted/30 p-4">
            <p className="text-sm text-muted-foreground">
              {t("frontend.whatsapp_link.demo_description")}
            </p>
            <a
              href="/admin/demo/simulator"
              className="inline-flex min-h-11 items-center justify-center gap-2 rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground transition-colors hover:bg-primary/90 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
            >
              {t("frontend.whatsapp_link.demo_simulator_link")}
              <ExternalLink className="size-4" aria-hidden="true" />
            </a>
          </div>
        )}

        {/* Connected: disconnect button */}
        {connected && !isDemo && (
          <div className="flex flex-col gap-3">
            <div className="flex gap-3">
              <AlertDialog open={disconnectDialogOpen} onOpenChange={setDisconnectDialogOpen}>
                <Button
                  variant="destructive"
                  onClick={() => setDisconnectDialogOpen(true)}
                  aria-label={t("frontend.whatsapp_link.disconnect")}
                >
                  {isDisconnecting ? (
                    <>
                      <Loader2 className="size-4 animate-spin" data-icon="inline-start" />
                      {t("frontend.whatsapp_link.disconnecting")}
                    </>
                  ) : (
                    t("frontend.whatsapp_link.disconnect")
                  )}
                </Button>

                <AlertDialogContent>
                  <AlertDialogHeader>
                    <AlertDialogTitle>{t("frontend.whatsapp_link.disconnect_confirm_title")}</AlertDialogTitle>
                    <AlertDialogDescription>
                      {t("frontend.whatsapp_link.disconnect_confirm_description")}
                    </AlertDialogDescription>
                  </AlertDialogHeader>
                  <AlertDialogFooter>
                    <AlertDialogCancel disabled={isDisconnecting}>{t("frontend.common.cancel")}</AlertDialogCancel>
                    <AlertDialogAction onClick={handleDisconnectConfirm} disabled={isDisconnecting}>
                      {isDisconnecting ? t("frontend.whatsapp_link.disconnecting") : t("frontend.whatsapp_link.disconnect")}
                    </AlertDialogAction>
                  </AlertDialogFooter>
                </AlertDialogContent>
              </AlertDialog>
            </div>
          </div>
        )}

        {/* Pairing tabs (disconnected + phone exists) */}
        {!connected && hasPhone && !isDemo && (
          <Tabs defaultValue="pairing-code">
            <TabsList>
              <TabsTrigger value="pairing-code">{t("frontend.whatsapp_link.pairing_tab")}</TabsTrigger>
              <TabsTrigger value="qr-code">{t("frontend.whatsapp_link.qr_tab")}</TabsTrigger>
            </TabsList>

            {/* Pairing code tab */}
            <TabsContent value="pairing-code" className="flex flex-col gap-4 pt-4">
              {!pairingCode ? (
                <div className="flex flex-col gap-3">
                  <p className="text-sm text-muted-foreground">
                    {t("frontend.whatsapp_link.pairing_code_instructions")}
                  </p>
                  <div>
                    <Button
                      onClick={handleRequestPairingCode}
                      disabled={isRequestingPair}
                      aria-label={t("frontend.whatsapp_link.generate_code")}
                    >
                      {isRequestingPair ? (
                        <>
                          <Loader2 className="size-4 animate-spin" data-icon="inline-start" />
                          {t("frontend.whatsapp_link.generating_code")}
                        </>
                      ) : (
                        t("frontend.whatsapp_link.generate_code")
                      )}
                    </Button>
                  </div>
                  {pairError && (
                    <Alert variant="destructive">
                      <AlertDescription>{pairError}</AlertDescription>
                    </Alert>
                  )}
                </div>
              ) : (
                <div className="flex flex-col gap-3">
                  <div className="flex flex-col items-center gap-2 rounded-lg border bg-muted/30 p-6">
                    <span className="text-xs text-muted-foreground">{t("frontend.whatsapp_link.pairing_code_label")}</span>
                    <span className="font-mono text-3xl font-bold tracking-widest" data-testid="pairing-code">
                      {pairingCode}
                    </span>
                  </div>
                  <p className="text-sm text-muted-foreground">
                    {t("frontend.whatsapp_link.pairing_code_instructions")}
                  </p>
                </div>
              )}

              {/* Timeout alert */}
              {timeoutError && (
                <Alert variant="destructive">
                  <AlertTitle>{t("frontend.whatsapp_link.error_timeout")}</AlertTitle>
                  <AlertDescription>
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={handleRetry}
                      className="mt-2"
                      aria-label={t("frontend.whatsapp_link.retry")}
                    >
                      {t("frontend.whatsapp_link.retry")}
                    </Button>
                  </AlertDescription>
                </Alert>
              )}
            </TabsContent>

            {/* QR code tab */}
            <TabsContent value="qr-code" className="flex flex-col gap-4 pt-4">
              {!qrCode ? (
                <div className="flex flex-col gap-3">
                  <p className="text-sm text-muted-foreground">
                    {t("frontend.whatsapp_link.qr_instructions")}
                  </p>
                  <div>
                    <Button
                      onClick={handleLoadQrCode}
                      disabled={isRequestingQr}
                      aria-label={t("frontend.whatsapp_link.refresh_qr")}
                    >
                      {isRequestingQr ? (
                        <>
                          <Loader2 className="size-4 animate-spin" data-icon="inline-start" />
                          {t("frontend.whatsapp_link.refreshing_qr")}
                        </>
                      ) : (
                        <>
                          <QrCode className="size-4" data-icon="inline-start" />
                          {t("frontend.whatsapp_link.refresh_qr")}
                        </>
                      )}
                    </Button>
                  </div>
                  {qrError && (
                    <Alert variant="destructive">
                      <AlertDescription>{qrError}</AlertDescription>
                    </Alert>
                  )}
                </div>
              ) : (
                <div className="flex flex-col items-center gap-4">
                  <div className="rounded-lg border bg-white p-2">
                    <img
                      src={getQrImageSrc(qrCode)}
                      alt={t("frontend.whatsapp_link.qr_alt")}
                      className="size-48 object-contain"
                    />
                  </div>
                  <p className="text-sm text-muted-foreground">{t("frontend.whatsapp_link.qr_instructions")}</p>
                  <div className="flex gap-3">
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={handleLoadQrCode}
                      disabled={isRequestingQr}
                      aria-label={t("frontend.whatsapp_link.refresh_qr")}
                    >
                      {isRequestingQr ? (
                        <>
                          <Loader2 className="size-3 animate-spin" data-icon="inline-start" />
                          {t("frontend.whatsapp_link.refreshing_qr")}
                        </>
                      ) : (
                        t("frontend.whatsapp_link.refresh_qr")
                      )}
                    </Button>
                  </div>

                  {/* Timeout alert */}
                  {timeoutError && (
                    <Alert variant="destructive" className="w-full">
                      <AlertTitle>{t("frontend.whatsapp_link.error_timeout")}</AlertTitle>
                      <AlertDescription>
                        <Button
                          variant="outline"
                          size="sm"
                          onClick={handleRetry}
                          className="mt-2"
                          aria-label={t("frontend.whatsapp_link.retry")}
                        >
                          {t("frontend.whatsapp_link.retry")}
                        </Button>
                      </AlertDescription>
                    </Alert>
                  )}
                </div>
              )}
            </TabsContent>
          </Tabs>
        )}
      </CardContent>
    </Card>
  );
}
