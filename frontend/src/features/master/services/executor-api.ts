import api from "@/lib/api";
import { t } from "@/i18n";

export type LookupExecutorLifecycleStatus = "draft" | "active" | "disabled";
export type LookupExecutorHealthStatus = "unknown" | "healthy" | "unhealthy";
export type LookupExecutorTransportMode = "https" | "http_encrypted";

export interface LookupExecutor {
  id: string;
  name: string;
  provider_label: string;
  base_url: string;
  transport_mode: LookupExecutorTransportMode;
  lifecycle_status: LookupExecutorLifecycleStatus;
  health_status: LookupExecutorHealthStatus;
  requires_reverification: boolean;
  max_concurrency: number;
  secret_version: number;
  pending_secret_version: number | null;
  has_hosting_password: boolean;
  last_verified_at: string | null;
  last_health_check_at: string | null;
  last_success_at: string | null;
  last_error_safe: string | null;
  active_jobs: number;
  created_at: string;
  updated_at: string;
}

export interface LookupExecutorCreateRequest {
  name: string;
  provider_label: string;
  base_url?: string;
  transport_mode?: LookupExecutorTransportMode;
  max_concurrency?: number;
  hosting_account_email?: string | null;
  hosting_account_password?: string | null;
  dashboard_url?: string | null;
}

export interface LookupExecutorUpdateRequest {
  name?: string;
  provider_label?: string;
  base_url?: string;
  transport_mode?: LookupExecutorTransportMode;
  max_concurrency?: number;
  hosting_account_email?: string | null;
  hosting_account_password?: string | null;
  dashboard_url?: string | null;
}

export interface LookupExecutorVerifyRequest {
  confirmation?: string;
  password?: string;
}

export interface LookupExecutorRevealRequest {
  password: string;
}

export interface LookupExecutorEnrollment {
  executor: LookupExecutor;
  plain_secret: string;
}

export interface LookupExecutorTestResult {
  status: "healthy";
  protocol_version: number;
  runtime_version: string;
  max_concurrency: number;
  executor: LookupExecutor;
}

export interface HostingPasswordResponse {
  hosting_account_password: string;
}

export async function fetchLookupExecutors(): Promise<LookupExecutor[]> {
  const { data } = await api.get<LookupExecutor[]>("/lookup-executors/");
  return data;
}

export async function fetchLookupExecutor(executorId: string): Promise<LookupExecutor> {
  const { data } = await api.get<LookupExecutor>(`/lookup-executors/${executorId}`);
  return data;
}

export async function createLookupExecutor(
  payload: LookupExecutorCreateRequest,
): Promise<LookupExecutorEnrollment> {
  const { data } = await api.post<LookupExecutorEnrollment>(
    "/lookup-executors/",
    payload,
  );
  return data;
}

export async function updateLookupExecutor(
  executorId: string,
  payload: LookupExecutorUpdateRequest,
): Promise<LookupExecutor> {
  const { data } = await api.put<LookupExecutor>(
    `/lookup-executors/${executorId}`,
    payload,
  );
  return data;
}

export async function verifyLookupExecutor(
  executorId: string,
  payload: LookupExecutorVerifyRequest = {},
): Promise<LookupExecutor> {
  const { data } = await api.post<LookupExecutor>(
    `/lookup-executors/${executorId}/verify`,
    payload,
  );
  return data;
}

export async function testLookupExecutor(
  executorId: string,
): Promise<LookupExecutorTestResult> {
  const { data } = await api.post<LookupExecutorTestResult>(
    `/lookup-executors/${executorId}/test`,
  );
  return data;
}

export async function enableLookupExecutor(executorId: string): Promise<LookupExecutor> {
  const { data } = await api.post<LookupExecutor>(
    `/lookup-executors/${executorId}/enable`,
  );
  return data;
}

export async function disableLookupExecutor(executorId: string): Promise<LookupExecutor> {
  const { data } = await api.post<LookupExecutor>(
    `/lookup-executors/${executorId}/disable`,
  );
  return data;
}

export async function rotateLookupExecutorSecret(
  executorId: string,
): Promise<LookupExecutorEnrollment> {
  const { data } = await api.post<LookupExecutorEnrollment>(
    `/lookup-executors/${executorId}/rotate-secret`,
  );
  return data;
}

export async function revealLookupExecutorHostingPassword(
  executorId: string,
  payload: LookupExecutorRevealRequest,
): Promise<HostingPasswordResponse> {
  const { data } = await api.post<HostingPasswordResponse>(
    `/lookup-executors/${executorId}/reveal-hosting-password`,
    payload,
  );
  return data;
}

export async function deleteLookupExecutor(executorId: string): Promise<void> {
  await api.delete(`/lookup-executors/${executorId}`);
}

const executorErrorKeys: Record<string, string> = {
  executor_not_found: "frontend.master.executors.error_not_found",
  executor_verification_failed: "frontend.master.executors.error_verification_failed",
  invalid_master_password: "frontend.master.executors.error_invalid_master_password",
  executor_coordination_unavailable:
    "frontend.master.executors.error_coordination_unavailable",
  executor_has_active_jobs: "frontend.master.executors.error_active_jobs",
  executor_has_active_leases: "frontend.master.executors.error_active_leases",
  step_up_unavailable: "frontend.master.executors.error_step_up_unavailable",
  insecure_http_confirmation_required:
    "frontend.master.executors.error_insecure_http_confirmation_required",
  executor_requires_verification:
    "frontend.master.executors.error_requires_verification",
  step_up_rate_limited: "frontend.master.executors.error_step_up_rate_limited",
  hosting_password_not_configured:
    "frontend.master.executors.error_hosting_password_missing",
};

export function mapExecutorError(error: unknown, fallbackKey: string): string {
  const detail = (
    error as { response?: { data?: { detail?: unknown } } }
  ).response?.data?.detail;
  const code = typeof detail === "string" ? detail : undefined;
  return t(code ? executorErrorKeys[code] ?? fallbackKey : fallbackKey);
}
