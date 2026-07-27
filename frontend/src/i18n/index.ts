import api from "@/lib/api";

let catalog: Record<string, string> = {};
let currentLocale = "en";
let _ready = false;
let _readyListeners: (() => void)[] = [];

export async function loadCatalog(locale?: string): Promise<void> {
  try {
    const response = locale
      ? api.get("/i18n/catalog", { params: { locale } })
      : api.get("/i18n/catalog");
    const { data } = await response;
    catalog = data.catalog || {};
    currentLocale = data.locale || "en";
  } catch {
    // Fallback: catalog stays empty, t() returns keys
  }
  _ready = true;
  _readyListeners.forEach((fn) => fn());
  _readyListeners = [];
}

export function isCatalogReady(): boolean {
  return _ready;
}

export function waitForCatalog(): Promise<void> {
  if (_ready) return Promise.resolve();
  return new Promise((resolve) => _readyListeners.push(resolve));
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
