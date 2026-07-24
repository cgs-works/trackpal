import { useState } from "react";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Loader2, Lock, Database, Download, XCircle, AlertCircle, CheckCircle2 } from "lucide-react";
import { masterRequestExport, masterCancelExport, masterGetExportStatus, masterGetExportDownloadUrl, type ExportJobStatusResponse } from "../services/tenant-api";

interface ExportDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  tenantId: string;
  tenantName: string;
}

export function ExportDialog({ open, onOpenChange, tenantId, tenantName }: ExportDialogProps) {
  const [step, setStep] = useState<"password" | "status">("password");
  const [password, setPassword] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [job, setJob] = useState<ExportJobStatusResponse | null>(null);

  function handleClose() {
    onOpenChange(false);
    // Reset state after animation
    setTimeout(() => {
      setStep("password");
      setPassword("");
      setLoading(false);
      setError(null);
      setJob(null);
    }, 200);
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!password.trim()) return;

    setLoading(true);
    setError(null);

    try {
      const result = await masterRequestExport(tenantId, password);
      setJob(result);
      setStep("status");
    } catch (err: any) {
      const msg = err?.response?.data?.detail || "Could not request export. Check your password.";
      setError(msg);
    } finally {
      setLoading(false);
    }
  }

  async function handleCancel() {
    if (!job) return;
    setLoading(true);
    try {
      await masterCancelExport(tenantId);
      // Refresh status
      const updated = await masterGetExportStatus(tenantId);
      if (updated) setJob(updated);
    } catch (err: any) {
      setError(err?.response?.data?.detail || "Could not cancel export.");
    } finally {
      setLoading(false);
    }
  }

  async function handleDownload() {
    setLoading(true);
    try {
      const result = await masterGetExportDownloadUrl(tenantId);
      const anchor = document.createElement("a");
      anchor.href = result.download_url;
      anchor.target = "_blank";
      anchor.rel = "noopener noreferrer";
      anchor.click();
    } catch (err: any) {
      setError(err?.response?.data?.detail || "Could not get download URL.");
    } finally {
      setLoading(false);
    }
  }

  // ── Password step ──────────────────────────────────────────

  if (step === "password") {
    return (
      <Dialog open={open} onOpenChange={(o) => { if (!o) handleClose(); }}>
        <DialogContent className="sm:max-w-md">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2">
              <Database className="size-5" />
              Export Data — {tenantName}
            </DialogTitle>
            <DialogDescription>
              Enter your Master password to authorize the export. The export will
              be shared with the business administrator and counts toward the 24-hour
              cooldown.
            </DialogDescription>
          </DialogHeader>

          <form onSubmit={handleSubmit}>
            <div className="space-y-4 py-2">
              <div className="space-y-2">
                <Label htmlFor="master-export-password">
                  <Lock className="mr-1 inline size-3.5" />
                  Master Password
                </Label>
                <Input
                  id="master-export-password"
                  type="password"
                  placeholder="Enter your Master password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  autoFocus
                />
              </div>

              {error && (
                <div className="flex items-start gap-2 rounded-md bg-destructive/10 p-3 text-sm text-destructive">
                  <AlertCircle className="mt-0.5 size-4 shrink-0" />
                  <span>{error}</span>
                </div>
              )}
            </div>

            <DialogFooter>
              <Button type="button" variant="outline" onClick={handleClose}>
                Cancel
              </Button>
              <Button type="submit" disabled={loading || !password.trim()}>
                {loading ? (
                  <>
                    <Loader2 className="mr-2 size-4 animate-spin" />
                    Requesting Export...
                  </>
                ) : (
                  "Request Export"
                )}
              </Button>
            </DialogFooter>
          </form>
        </DialogContent>
      </Dialog>
    );
  }

  // ── Status step ────────────────────────────────────────────

  const statusConfig = () => {
    switch (job?.status) {
      case "pending":
      case "processing":
        return {
          icon: <Loader2 className="size-10 animate-spin text-primary" />,
          label: job.status === "pending" ? "Pending..." : "Processing...",
          description: "The export is being generated. This may take a moment.",
        };
      case "ready":
        return {
          icon: <CheckCircle2 className="size-10 text-green-600" />,
          label: "Ready for Download",
          description: job.artifact_size_bytes
            ? `Export ready — ${formatBytes(job.artifact_size_bytes)}`
            : "Export ready for download.",
        };
      case "failed":
        return {
          icon: <AlertCircle className="size-10 text-destructive" />,
          label: "Failed",
          description: job.error_code
            ? `Error: ${job.error_code}`
            : "The export could not be generated.",
        };
      case "cancelled":
        return {
          icon: <XCircle className="size-10 text-muted-foreground" />,
          label: "Cancelled",
          description: "The export request was cancelled.",
        };
      default:
        return {
          icon: <Database className="size-10 text-muted-foreground" />,
          label: "Unknown",
          description: "Unknown export status.",
        };
    }
  };

  const config = statusConfig();

  return (
    <Dialog open={open} onOpenChange={(o) => { if (!o) handleClose(); }}>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <Database className="size-5" />
            Export Data — {tenantName}
          </DialogTitle>
        </DialogHeader>

        <div className="flex flex-col items-center gap-3 py-6 text-center">
          <div className="flex size-16 items-center justify-center rounded-full bg-muted">
            {config.icon}
          </div>
          <div>
            <p className="font-semibold">{config.label}</p>
            <p className="text-sm text-muted-foreground">{config.description}</p>
          </div>

          {error && (
            <div className="flex items-start gap-2 rounded-md bg-destructive/10 p-3 text-sm text-destructive">
              <AlertCircle className="mt-0.5 size-4 shrink-0" />
              <span>{error}</span>
            </div>
          )}
        </div>

        <DialogFooter className="flex flex-wrap gap-2 sm:justify-center">
          {/* Download */}
          {(job?.status === "ready") && (
            <Button type="button" onClick={handleDownload} disabled={loading}>
              {loading ? (
                <><Loader2 className="mr-2 size-4 animate-spin" /> Loading...</>
              ) : (
                <><Download className="mr-2 size-4" /> Download</>
              )}
            </Button>
          )}

          {/* Cancel */}
          {(job?.status === "pending" || job?.status === "processing") && (
            <Button type="button" variant="secondary" onClick={handleCancel} disabled={loading}>
              {loading ? (
                <><Loader2 className="mr-2 size-4 animate-spin" /> Cancelling...</>
              ) : (
                <><XCircle className="mr-2 size-4" /> Cancel</>
              )}
            </Button>
          )}

          <Button type="button" variant="outline" onClick={handleClose}>
            Close
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}
