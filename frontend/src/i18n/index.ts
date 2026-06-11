import api from "@/lib/api";

let catalog: Record<string, string> = {};
let currentLocale = "en";

export async function loadCatalog(): Promise<void> {
  try {
    const { data } = await api.get("/i18n/catalog");
    catalog = data.catalog || {};
    currentLocale = data.locale || "en";
  } catch {
    // Fallback: catalog stays empty, t() returns keys
  }
}

export function t(key: string, params?: Record<string, string | number>): string {
  let value = catalog[key] || key;
  if (params) {
    for (const [k, v] of Object.entries(params)) {
      value = value.replace(new RegExp(`\\{${k}\\}`, "g"), String(v));
    }
  }
  return value;
}

export function getLocale(): string {
  return currentLocale;
}
