export function getApiError(error: unknown, fallback: string): string {
  const err = error as { response?: { data?: { detail?: string | Array<{ msg?: string }> } } };
  const detail = err.response?.data?.detail;
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail)) return detail.map((item) => item.msg || String(item)).join(", ");
  return error instanceof Error ? error.message : fallback;
}
