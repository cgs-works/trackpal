export const ICON_REFERENCE_PATTERN =
  /^[a-z0-9]+(?:-[a-z0-9]+)*:[a-z0-9]+(?:-[a-z0-9]+)*$/;

export function parseIconReference(
  value: string | null | undefined,
): { prefix: string; name: string } | null {
  if (!value || value.length > 255 || !ICON_REFERENCE_PATTERN.test(value))
    return null;
  const separator = value.indexOf(":");
  return { prefix: value.slice(0, separator), name: value.slice(separator + 1) };
}
