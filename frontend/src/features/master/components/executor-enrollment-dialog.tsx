import { useEffect, useState, type FormEvent } from "react";
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
import {
  Select,
  SelectContent,
  SelectGroup,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { t } from "@/i18n";
import {
  createLookupExecutor,
  enableLookupExecutor,
  mapExecutorError,
  testLookupExecutor,
  updateLookupExecutor,
  verifyLookupExecutor,
  type LookupExecutor,
  type LookupExecutorEnrollment,
  type LookupExecutorTestResult,
  type LookupExecutorTransportMode,
} from "../services/executor-api";
import { ExecutorCredentialsDialog } from "./executor-credentials-dialog";

type EnrollmentStep = "identity" | "credentials" | "connection" | "activation";

interface ExecutorEnrollmentDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onCompleted?: (executor: LookupExecutor) => void;
}

interface IdentityForm {
  name: string;
  provider_label: string;
  max_concurrency: string;
  hosting_account_email: string;
  hosting_account_password: string;
  dashboard_url: string;
}

const initialIdentity: IdentityForm = {
  name: "",
  provider_label: "",
  max_concurrency: "1",
  hosting_account_email: "",
  hosting_account_password: "",
  dashboard_url: "",
};

export function ExecutorEnrollmentDialog({
  open,
  onOpenChange,
  onCompleted,
}: ExecutorEnrollmentDialogProps) {
  const [step, setStep] = useState<EnrollmentStep>("identity");
  const [identity, setIdentity] = useState<IdentityForm>(initialIdentity);
  const [executorId, setExecutorId] = useState("");
  const [credentials, setCredentials] = useState<LookupExecutorEnrollment | null>(null);
  const [baseUrl, setBaseUrl] = useState("");
  const [transportMode, setTransportMode] = useState<LookupExecutorTransportMode>("https");
  const [configuredCapacity, setConfiguredCapacity] = useState("1");
  const [testResult, setTestResult] = useState<LookupExecutorTestResult | null>(null);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");

  function resetWizard() {
    setStep("identity");
    setIdentity(initialIdentity);
    setExecutorId("");
    setCredentials(null);
    setBaseUrl("");
    setTransportMode("https");
    setConfiguredCapacity("1");
    setTestResult(null);
    setSaving(false);
    setError("");
  }

  useEffect(() => {
    if (!open) resetWizard();
  }, [open]);

  function close() {
    setCredentials(null);
    onOpenChange(false);
  }

  async function createDraft(event: FormEvent) {
    event.preventDefault();
    setError("");
    const maxConcurrency = Number(identity.max_concurrency);
    if (!identity.name.trim() || !identity.provider_label.trim() || !Number.isInteger(maxConcurrency) || maxConcurrency < 1) {
      return;
    }

    setSaving(true);
    try {
      const payload = {
        name: identity.name.trim(),
        provider_label: identity.provider_label.trim(),
        max_concurrency: maxConcurrency,
        ...(identity.hosting_account_email.trim() && {
          hosting_account_email: identity.hosting_account_email.trim(),
        }),
        ...(identity.hosting_account_password && {
          hosting_account_password: identity.hosting_account_password,
        }),
        ...(identity.dashboard_url.trim() && {
          dashboard_url: identity.dashboard_url.trim(),
        }),
      };
      const enrollment = await createLookupExecutor(payload);
      setExecutorId(enrollment.executor.id);
      setCredentials(enrollment);
      setBaseUrl(enrollment.executor.base_url);
      setTransportMode(enrollment.executor.transport_mode);
      setConfiguredCapacity(String(maxConcurrency));
      setStep("credentials");
    } catch (createError) {
      setError(mapExecutorError(createError, "frontend.master.executors.error_create"));
    } finally {
      setSaving(false);
    }
  }

  function dismissCredentials() {
    setCredentials(null);
    setStep("connection");
  }

  async function verifyConnection(event: FormEvent) {
    event.preventDefault();
    setError("");
    const maxConcurrency = Number(configuredCapacity);
    if (!baseUrl.trim() || !Number.isInteger(maxConcurrency) || maxConcurrency < 1) return;

    setSaving(true);
    try {
      await updateLookupExecutor(executorId, {
        base_url: baseUrl.trim(),
        transport_mode: transportMode,
        max_concurrency: maxConcurrency,
      });
      await verifyLookupExecutor(executorId);
      const result = await testLookupExecutor(executorId);
      if (maxConcurrency > result.max_concurrency) {
        setError(t("frontend.master.executors.error_capacity_exceeds_advertised"));
        return;
      }
      setTestResult(result);
      setStep("activation");
    } catch (verifyError) {
      setError(mapExecutorError(verifyError, "frontend.master.executors.error_verification_failed"));
    } finally {
      setSaving(false);
    }
  }

  async function activate() {
    setError("");
    setSaving(true);
    try {
      const executor = await enableLookupExecutor(executorId);
      onCompleted?.(executor);
      close();
    } catch (enableError) {
      setError(mapExecutorError(enableError, "frontend.master.executors.error_enable"));
    } finally {
      setSaving(false);
    }
  }

  return (
    <>
      <Dialog
        open={open}
        onOpenChange={(nextOpen) => {
          if (!saving && !nextOpen) close();
        }}
      >
        <DialogContent className="max-h-[min(90dvh,44rem)] overflow-y-auto sm:max-w-lg">
          <DialogHeader>
            <DialogTitle>{t("frontend.master.executors.wizard_title")}</DialogTitle>
            <DialogDescription>
              {t("frontend.master.executors.wizard_description")}
            </DialogDescription>
          </DialogHeader>

          <StepIndicator step={step} />
          {error && (
            <p role="alert" className="rounded-lg border border-destructive/20 bg-destructive/10 p-3 text-sm text-destructive">
              {error}
            </p>
          )}

          {step === "identity" && (
            <form onSubmit={createDraft} className="flex flex-col gap-4" aria-busy={saving}>
              <div className="flex flex-col gap-2">
                <Label htmlFor="executor-name">{t("frontend.master.executors.name")}</Label>
                <Input
                  id="executor-name"
                  value={identity.name}
                  onChange={(event) => updateIdentity("name", event.target.value)}
                  required
                  maxLength={255}
                  autoFocus
                  disabled={saving}
                />
              </div>
              <div className="flex flex-col gap-2">
                <Label htmlFor="executor-provider">{t("frontend.master.executors.provider")}</Label>
                <Input
                  id="executor-provider"
                  value={identity.provider_label}
                  onChange={(event) => updateIdentity("provider_label", event.target.value)}
                  required
                  maxLength={50}
                  disabled={saving}
                />
              </div>
              <div className="flex flex-col gap-2">
                <Label htmlFor="executor-capacity">{t("frontend.master.executors.max_concurrency")}</Label>
                <Input
                  id="executor-capacity"
                  type="number"
                  min={1}
                  step={1}
                  value={identity.max_concurrency}
                  onChange={(event) => updateIdentity("max_concurrency", event.target.value)}
                  required
                  disabled={saving}
                />
              </div>
              <OptionalHostingFields
                identity={identity}
                disabled={saving}
                onChange={updateIdentity}
              />
              <DialogFooter>
                <Button type="button" variant="outline" onClick={close} disabled={saving}>
                  {t("frontend.master.executors.cancel")}
                </Button>
                <Button type="submit" disabled={saving}>
                  {t("frontend.master.executors.next")}
                </Button>
              </DialogFooter>
            </form>
          )}

          {step === "connection" && (
            <form onSubmit={verifyConnection} className="flex flex-col gap-4" aria-busy={saving}>
              <div className="flex flex-col gap-2">
                <Label htmlFor="executor-base-url">{t("frontend.master.executors.base_url")}</Label>
                <Input
                  id="executor-base-url"
                  type="url"
                  value={baseUrl}
                  onChange={(event) => setBaseUrl(event.target.value)}
                  required
                  placeholder="https://executor.example.test"
                  disabled={saving}
                />
              </div>
              <div className="flex flex-col gap-2">
                <Label htmlFor="executor-transport">{t("frontend.master.executors.transport_mode")}</Label>
                <Select value={transportMode} onValueChange={(value) => {
                  if (value === "https" || value === "http_encrypted") setTransportMode(value);
                }}>
                  <SelectTrigger id="executor-transport" disabled={saving}>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectGroup>
                      <SelectItem value="https">{t("frontend.master.executors.transport_https")}</SelectItem>
                      <SelectItem value="http_encrypted">{t("frontend.master.executors.transport_http_encrypted")}</SelectItem>
                    </SelectGroup>
                  </SelectContent>
                </Select>
              </div>
              <div className="flex flex-col gap-2">
                <Label htmlFor="executor-configured-capacity">{t("frontend.master.executors.max_concurrency")}</Label>
                <Input
                  id="executor-configured-capacity"
                  type="number"
                  min={1}
                  step={1}
                  value={configuredCapacity}
                  onChange={(event) => setConfiguredCapacity(event.target.value)}
                  required
                  disabled={saving}
                />
              </div>
              <DialogFooter>
                <Button type="button" variant="outline" onClick={close} disabled={saving}>
                  {t("frontend.master.executors.cancel")}
                </Button>
                <Button type="submit" disabled={saving}>
                  {t("frontend.master.executors.verify")}
                </Button>
              </DialogFooter>
            </form>
          )}

          {step === "activation" && testResult && (
            <div className="flex flex-col gap-4">
              <div className="rounded-lg border p-4">
                <p className="font-medium">{t("frontend.master.executors.connection_healthy")}</p>
                <dl className="mt-3 grid grid-cols-2 gap-3 text-sm">
                  <div>
                    <dt className="text-muted-foreground">{t("frontend.master.executors.protocol_version")}</dt>
                    <dd>{testResult.protocol_version}</dd>
                  </div>
                  <div>
                    <dt className="text-muted-foreground">{t("frontend.master.executors.runtime_version")}</dt>
                    <dd>{testResult.runtime_version}</dd>
                  </div>
                  <div>
                    <dt className="text-muted-foreground">{t("frontend.master.executors.advertised_capacity")}</dt>
                    <dd>{t("frontend.master.executors.advertised_capacity_value", { maximum: testResult.max_concurrency })}</dd>
                  </div>
                </dl>
              </div>
              <DialogFooter>
                <Button type="button" variant="outline" onClick={close} disabled={saving}>
                  {t("frontend.master.executors.cancel")}
                </Button>
                <Button type="button" onClick={() => void activate()} disabled={saving}>
                  {t("frontend.master.executors.enable")}
                </Button>
              </DialogFooter>
            </div>
          )}
        </DialogContent>
      </Dialog>

      <ExecutorCredentialsDialog
        credentials={credentials}
        onDismiss={dismissCredentials}
      />
    </>
  );

  function updateIdentity(key: keyof IdentityForm, value: string) {
    setIdentity((current) => ({ ...current, [key]: value }));
  }
}

function StepIndicator({ step }: { step: EnrollmentStep }) {
  return (
    <p className="text-sm text-muted-foreground" aria-live="polite">
      {t(`frontend.master.executors.step_${step}`)}
    </p>
  );
}

function OptionalHostingFields({
  identity,
  disabled,
  onChange,
}: {
  identity: IdentityForm;
  disabled: boolean;
  onChange: (key: keyof IdentityForm, value: string) => void;
}) {
  return (
    <fieldset className="flex flex-col gap-3 rounded-lg border p-3">
      <legend className="px-1 text-sm font-medium">{t("frontend.master.executors.hosting_details")}</legend>
      <div className="flex flex-col gap-2">
        <Label htmlFor="executor-hosting-email">{t("frontend.master.executors.hosting_email")}</Label>
        <Input
          id="executor-hosting-email"
          type="email"
          value={identity.hosting_account_email}
          onChange={(event) => onChange("hosting_account_email", event.target.value)}
          disabled={disabled}
        />
      </div>
      <div className="flex flex-col gap-2">
        <Label htmlFor="executor-hosting-password">{t("frontend.master.executors.hosting_password")}</Label>
        <Input
          id="executor-hosting-password"
          type="password"
          value={identity.hosting_account_password}
          onChange={(event) => onChange("hosting_account_password", event.target.value)}
          disabled={disabled}
        />
      </div>
      <div className="flex flex-col gap-2">
        <Label htmlFor="executor-dashboard-url">{t("frontend.master.executors.dashboard_url")}</Label>
        <Input
          id="executor-dashboard-url"
          type="url"
          value={identity.dashboard_url}
          onChange={(event) => onChange("dashboard_url", event.target.value)}
          disabled={disabled}
        />
      </div>
    </fieldset>
  );
}
