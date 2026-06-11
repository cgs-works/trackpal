import catalog from "./public.json";

const STORAGE_KEY = "publicLocale";
const DEFAULT_LOCALE = "en";

type Locale = "en" | "es";

function loadFromStorage(): Locale {
  try {
    const stored = localStorage.getItem(STORAGE_KEY);
    if (stored === "en" || stored === "es") return stored;
  } catch {
    /* localStorage unavailable */
  }
  return DEFAULT_LOCALE;
}

let currentLocale: Locale = loadFromStorage();

const listeners = new Set<() => void>();

export function getLocale(): Locale {
  return currentLocale;
}

export function setLocale(value: Locale) {
  currentLocale = value;
  try {
    localStorage.setItem(STORAGE_KEY, value);
  } catch {
    /* localStorage unavailable */
  }
  for (const fn of listeners) fn();
}

export function subscribeLocale(fn: () => void): () => void {
  listeners.add(fn);
  return () => listeners.delete(fn);
}

export function t(key: string, params?: Record<string, string | number>): string {
  const strings =
    catalog[currentLocale as keyof typeof catalog] || catalog[DEFAULT_LOCALE];
  let template: string | undefined = strings[key as keyof typeof strings];

  if (template === undefined) {
    template = catalog[DEFAULT_LOCALE]?.[key as keyof (typeof catalog)["en"]];
  }
  if (template === undefined) {
    if (import.meta.env.DEV) {
      console.warn(`[publicI18n] Missing key: ${key}`);
    }
    return key;
  }
  if (params) {
    return Object.entries(params).reduce(
      (str, [k, v]) => str.replace(new RegExp(`\\{${k}\\}`, "g"), String(v)),
      template
    );
  }
  return template;
}
