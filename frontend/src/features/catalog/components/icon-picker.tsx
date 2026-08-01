import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Check, Loader2, Search, AlertCircle } from "lucide-react";
import { t } from "@/i18n";
import { iconifyCatalog, type IconCollectionInfo, type IconDetails } from "@/features/catalog/services/icon-catalog";
import { parseIconReference } from "@/features/catalog/services/icon-reference";
import { ServiceIcon } from "./service-icon";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";

const DEBOUNCE_MS = 300;
const MIN_QUERY_LENGTH = 2;

export interface IconPickerProps {
  open: boolean;
  value: string | null;
  initialQuery?: string;
  onOpenChange(open: boolean): void;
  onSelect(icon: string | null): void;
}

export function IconPicker({
  open,
  value,
  initialQuery = "",
  onOpenChange,
  onSelect,
}: IconPickerProps) {
  const [query, setQuery] = useState(initialQuery);
  const [results, setResults] = useState<string[]>([]);
  const [collections, setCollections] = useState<Record<string, IconCollectionInfo>>({});
  const [selected, setSelected] = useState<string | null>(value);
  const [selectedDetails, setSelectedDetails] = useState<IconDetails | null>(null);
  const [pageStart, setPageStart] = useState(0);
  const [pageSize, setPageSize] = useState(64);
  const [hasMore, setHasMore] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [searched, setSearched] = useState(false);
  const [resetKey, setResetKey] = useState(0);

  const abortRef = useRef<AbortController | null>(null);
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    if (!open) return;
    setResetKey((k) => k + 1);
    setQuery(initialQuery);
    setResults([]);
    setCollections({});
    setSelected(value);
    setSelectedDetails(null);
    setPageStart(0);
    setPageSize(64);
    setHasMore(false);
    setLoading(false);
    setError(null);
    setSearched(false);

    if (value) {
      const parsed = parseIconReference(value);
      if (parsed) {
        iconifyCatalog
          .describe(value)
          .then((details) => {
            setSelectedDetails(details);
          })
          .catch(() => {});
      }
    }
  }, [open, value, initialQuery]);

  useEffect(() => {
    return () => {
      if (timerRef.current) clearTimeout(timerRef.current);
      if (abortRef.current) abortRef.current.abort();
    };
  }, []);

  const performSearch = useCallback(
    async (q: string, start: number) => {
      if (abortRef.current) abortRef.current.abort();
      const controller = new AbortController();
      abortRef.current = controller;

      setLoading(true);
      setError(null);
      setSearched(true);

      try {
        const page = await iconifyCatalog.search(q, start, controller.signal);
        if (controller.signal.aborted) return;

        setResults((prev) => {
          const merged = start === 0 ? page.icons : [...prev, ...page.icons];
          return [...new Set(merged)];
        });
        setCollections((prev) => ({ ...prev, ...page.collections }));
        setPageStart(start);
        setPageSize(page.limit);
        setHasMore(page.hasMore);
      } catch {
        if (controller.signal.aborted) return;
        setError(t("frontend.icon_picker.error"));
      } finally {
        // Only clear loading if this controller is still the active one
        if (abortRef.current === controller && !controller.signal.aborted) {
          setLoading(false);
        }
      }
    },
    [],
  );

  useEffect(() => {
    if (timerRef.current) clearTimeout(timerRef.current);

    if (query.length < MIN_QUERY_LENGTH) {
      // Abort any in-flight search for the discarded query
      if (abortRef.current) abortRef.current.abort();
      setLoading(false);
      setResults([]);
      setCollections({});
      setPageStart(0);
      setHasMore(false);
      setSearched(false);
      setError(null);
      return;
    }

    timerRef.current = setTimeout(() => {
      performSearch(query, 0);
    }, DEBOUNCE_MS);

    return () => {
      if (timerRef.current) clearTimeout(timerRef.current);
    };
  }, [query, performSearch, resetKey]);

  const handleQueryChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    setQuery(e.target.value);
  };

  const handleSelectOption = (iconRef: string) => {
    setSelected(iconRef);
    const parsed = parseIconReference(iconRef);
    if (parsed && collections[parsed.prefix]) {
      setSelectedDetails({
        icon: iconRef,
        prefix: parsed.prefix,
        name: parsed.name,
        collection: collections[parsed.prefix],
      });
    }
  };

  const handleLoadMore = () => {
    if (loading || !hasMore) return;
    performSearch(query, pageStart + pageSize);
  };

  const handleRetry = () => {
    if (query.length >= MIN_QUERY_LENGTH) {
      performSearch(query, 0);
    }
  };

  const handleConfirm = () => {
    onSelect(selected);
    onOpenChange(false);
  };

  const handleOpenChange = (o: boolean) => {
    if (!o) onOpenChange(false);
  };

  const activeDetails: IconDetails | null = useMemo(() => {
    if (selectedDetails) return selectedDetails;
    if (results.length > 0) {
      const firstParsed = parseIconReference(results[0]);
      if (firstParsed && collections[firstParsed.prefix]) {
        return {
          icon: results[0],
          prefix: firstParsed.prefix,
          name: firstParsed.name,
          collection: collections[firstParsed.prefix],
        };
      }
    }
    return null;
  }, [selectedDetails, results, collections]);

  const canConfirm = Boolean(
    selected !== null &&
    selectedDetails?.collection.license.title &&
    selectedDetails.collection.license.url,
  );

  const optionLabel = (iconRef: string): string => {
    const parsed = parseIconReference(iconRef);
    if (!parsed) return iconRef;
    const coll = collections[parsed.prefix];
    const collName = coll?.name ?? parsed.prefix;
    return `${iconRef} — ${collName}`;
  };

  const statusMessage = loading
    ? t("frontend.icon_picker.searching")
    : searched && results.length > 0
      ? t("frontend.icon_picker.results", { count: results.length })
      : "";

  return (
    <Dialog open={open} onOpenChange={handleOpenChange}>
      <DialogContent className="max-h-[90vh] overflow-hidden sm:max-w-5xl">
        <DialogHeader>
          <DialogTitle>{t("frontend.icon_picker.title")}</DialogTitle>
          <DialogDescription>{t("frontend.icon_picker.description")}</DialogDescription>
        </DialogHeader>

        <div className="grid min-h-0 gap-4 md:grid-cols-[minmax(0,1fr)_18rem]">
          <section className="flex min-h-0 flex-col gap-3">
            <div className="relative">
              <Search className="pointer-events-none absolute left-2.5 top-1/2 size-4 -translate-y-1/2 text-muted-foreground" />
              <Input
                type="search"
                role="searchbox"
                placeholder={t("frontend.icon_picker.search_hint")}
                value={query}
                onChange={handleQueryChange}
                className="pl-8"
                aria-label={t("frontend.icon_picker.search")}
              />
            </div>

            <div aria-live="polite" className="sr-only">
              {statusMessage}
            </div>

            {loading && (
              <div className="flex items-center gap-2 text-sm text-muted-foreground">
                <Loader2 className="size-4 animate-spin" />
                {t("frontend.icon_picker.searching")}
              </div>
            )}

            {error && (
              <div className="flex items-center gap-2 rounded-lg bg-destructive/10 p-3 text-sm text-destructive">
                <AlertCircle className="size-4 shrink-0" />
                {error}
              </div>
            )}

            {!loading && searched && results.length === 0 && !error && (
              <p className="text-sm text-muted-foreground">
                {t("frontend.icon_picker.empty")}
              </p>
            )}

            {results.length > 0 && (
              <div
                role="listbox"
                aria-label={t("frontend.icon_picker.search")}
                className="flex flex-col gap-1 overflow-y-auto"
              >
                {results.map((iconRef) => {
                  const isSelected = selected === iconRef;
                  const parsed = parseIconReference(iconRef);
                  const collName = parsed && collections[parsed.prefix]
                    ? collections[parsed.prefix].name
                    : parsed?.prefix ?? "";

                  return (
                    <button
                      key={iconRef}
                      type="button"
                      role="option"
                      aria-selected={isSelected}
                      aria-label={optionLabel(iconRef)}
                      onClick={() => handleSelectOption(iconRef)}
                      className="flex items-center gap-3 rounded-lg border p-2 text-left text-sm transition-colors hover:bg-muted data-[selected]:border-primary data-[selected]:bg-primary/5"
                      data-selected={isSelected ? "" : undefined}
                    >
                      <ServiceIcon icon={iconRef} label={collName} className="size-6" />
                      <span className="flex-1 truncate font-medium">{iconRef}</span>
                      {isSelected && (
                        <Check
                          data-testid="icon-picker-selected-marker"
                          className="size-4 shrink-0 text-primary"
                        />
                      )}
                    </button>
                  );
                })}
              </div>
            )}

            {hasMore && !loading && (
              <Button type="button" variant="outline" onClick={handleLoadMore}>
                {t("frontend.icon_picker.load_more")}
              </Button>
            )}

            {error && (
              <Button type="button" variant="outline" onClick={handleRetry}>
                {t("frontend.icon_picker.retry")}
              </Button>
            )}
          </section>

          <aside
            data-testid="icon-picker-details"
            className="order-last rounded-lg border p-4 md:order-none"
          >
            {activeDetails ? (
              <div className="flex flex-col gap-3">
                <div className="flex items-center gap-3">
                  <ServiceIcon
                    icon={activeDetails.icon}
                    label={activeDetails.name}
                    className="size-10"
                  />
                  <div className="min-w-0">
                    <p className="truncate text-sm font-medium">{activeDetails.icon}</p>
                    <p className="truncate text-xs text-muted-foreground">
                      {activeDetails.collection.name}
                    </p>
                  </div>
                </div>

                <div className="flex flex-col gap-1 text-xs">
                  <p>
                    <span className="text-muted-foreground">{t("frontend.icon_picker.collection")}: </span>
                    {activeDetails.collection.name}
                  </p>
                  {activeDetails.collection.author.name && (
                    <p>
                      <span className="text-muted-foreground">{t("frontend.icon_picker.author")}: </span>
                      {activeDetails.collection.author.name}
                    </p>
                  )}
                  {activeDetails.collection.license.title && (
                    <p>
                      <span className="text-muted-foreground">{t("frontend.icon_picker.license")}: </span>
                      {activeDetails.collection.license.url ? (
                        <a
                          href={activeDetails.collection.license.url}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="underline underline-offset-2 hover:text-foreground"
                        >
                          {activeDetails.collection.license.title}
                        </a>
                      ) : (
                        activeDetails.collection.license.title
                      )}
                    </p>
                  )}
                </div>

                {(!activeDetails.collection.license.title || !activeDetails.collection.license.url) && (
                  <p className="text-xs text-muted-foreground">
                    {t("frontend.icon_picker.license_unavailable")}
                  </p>
                )}
              </div>
            ) : (
              <p className="text-sm text-muted-foreground">
                {t("frontend.icon_picker.selected")}
              </p>
            )}
          </aside>
        </div>

        <DialogFooter>
          <Button type="button" variant="outline" onClick={() => handleOpenChange(false)}>
            {t("frontend.icon_picker.cancel")}
          </Button>
          <Button type="button" onClick={handleConfirm} disabled={!canConfirm}>
            {t("frontend.icon_picker.select")}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
