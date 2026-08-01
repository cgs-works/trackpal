import { parseIconReference } from "./icon-reference";

const SEARCH_LIMIT = 64;
const API_BASE = "https://api.iconify.design";

export interface IconAuthor {
  name: string;
  url?: string;
}

export interface IconLicense {
  title: string;
  spdx?: string;
  url: string;
}

export interface IconCollectionInfo {
  prefix: string;
  name: string;
  author: IconAuthor;
  license: IconLicense;
  palette: boolean;
}

export interface IconSearchPage {
  icons: string[];
  total: number;
  limit: number;
  start: number;
  hasMore: boolean;
  collections: Record<string, IconCollectionInfo>;
}

export interface IconDetails {
  icon: string;
  prefix: string;
  name: string;
  collection: IconCollectionInfo;
}

export interface IconCatalog {
  search(
    query: string,
    start?: number,
    signal?: AbortSignal,
  ): Promise<IconSearchPage>;
  describe(icon: string, signal?: AbortSignal): Promise<IconDetails>;
}

type Fetcher = typeof fetch;

function normalizeCollection(
  prefix: string,
  raw: Record<string, unknown>,
): IconCollectionInfo {
  const c = raw as Record<string, unknown>;
  const author = (c.author ?? {}) as Record<string, unknown>;
  const license = (c.license ?? {}) as Record<string, unknown>;
  return {
    prefix,
    name: String(c.name ?? prefix),
    author: {
      name: String(author.name ?? c.name ?? prefix),
      ...(author.url ? { url: String(author.url) } : {}),
    },
    license: {
      title: String(license.title ?? ""),
      ...(license.spdx ? { spdx: String(license.spdx) } : {}),
      url: String(license.url ?? ""),
    },
    palette: Boolean(c.palette),
  };
}

export function createIconifyCatalog(fetcher: Fetcher = fetch): IconCatalog {
  const searchCache = new Map<string, IconSearchPage>();
  const collectionCache = new Map<string, IconCollectionInfo>();

  async function search(
    query: string,
    start = 0,
    signal?: AbortSignal,
  ): Promise<IconSearchPage> {
    const trimmed = query.trim();
    const cacheKey = `${trimmed.toLocaleLowerCase()}:${start}`;
    const cached = searchCache.get(cacheKey);
    if (cached) return cached;

    const url = new URL(`${API_BASE}/search`);
    url.searchParams.set("query", trimmed);
    url.searchParams.set("limit", String(SEARCH_LIMIT));
    url.searchParams.set("start", String(start));

    const res = await fetcher(String(url), { signal });
    if (!res.ok) throw new Error("iconify_search_failed");

    const body = (await res.json()) as Record<string, unknown>;
    const icons = (body.icons ?? []) as string[];
    const total = Number(body.total ?? 0);
    const rawCollections = (body.collections ?? {}) as Record<
      string,
      Record<string, unknown>
    >;

    const collections: Record<string, IconCollectionInfo> = {};
    for (const [prefix, raw] of Object.entries(rawCollections)) {
      collections[prefix] = normalizeCollection(prefix, raw);
    }

    const page: IconSearchPage = {
      icons,
      total,
      limit: SEARCH_LIMIT,
      start,
      hasMore: start + icons.length < total,
      collections,
    };

    searchCache.set(cacheKey, page);
    return page;
  }

  async function describe(
    icon: string,
    signal?: AbortSignal,
  ): Promise<IconDetails> {
    const parsed = parseIconReference(icon);
    if (!parsed) throw new Error("iconify_icon_invalid");

    const cached = collectionCache.get(parsed.prefix);
    if (cached) {
      return { icon, prefix: parsed.prefix, name: parsed.name, collection: cached };
    }

    const url = new URL(`${API_BASE}/collections`);
    url.searchParams.set("prefix", parsed.prefix);

    const res = await fetcher(String(url), { signal });
    if (!res.ok) throw new Error("iconify_search_failed");

    const body = (await res.json()) as Record<string, Record<string, unknown>>;
    const raw = body[parsed.prefix];
    if (!raw) throw new Error("iconify_icon_invalid");

    const collection = normalizeCollection(parsed.prefix, raw);
    collectionCache.set(parsed.prefix, collection);

    return { icon, prefix: parsed.prefix, name: parsed.name, collection };
  }

  return { search, describe };
}

export const iconifyCatalog = createIconifyCatalog();
