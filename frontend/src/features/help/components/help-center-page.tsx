import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Link, Navigate } from "@tanstack/react-router";
import { BookOpen, Menu, Search, X } from "lucide-react";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { buttonVariants } from "@/components/ui/button";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import {
  Sheet,
  SheetContent,
  SheetHeader,
  SheetTitle,
} from "@/components/ui/sheet";
import { Skeleton } from "@/components/ui/skeleton";
import { t } from "@/i18n";
import { useAuthStore } from "@/store/auth";
import { isPrivateHelpEnabled } from "../config";
import {
  getHelpIndex,
  getHelpTopic,
  searchHelp,
  type HelpIndexResponse,
  type HelpSearchResult,
  type HelpTopic,
  type HelpTopicSummary,
} from "../services/help-api";
import { SafeMarkdown } from "./safe-markdown";
import { resolveSafeHelpNavigation } from "../safe-navigation";

type HelpListItem = HelpTopicSummary | HelpSearchResult;
export type HelpAudience = "tenant" | "client";

type HelpModule =
  | "dashboard"
  | "clients"
  | "catalog"
  | "subscriptions"
  | "settings"
  | "profile"
  | "password"
  | "help";

const ADMIN_HELP_MODULE_ORDER: HelpModule[] = [
  "dashboard",
  "clients",
  "catalog",
  "subscriptions",
  "settings",
  "help",
];

const CLIENT_HELP_MODULE_ORDER: HelpModule[] = [
  "dashboard",
  "profile",
  "subscriptions",
  "password",
  "help",
];

const HELP_MODULE_LABEL_KEYS: Record<HelpModule, string> = {
  dashboard: "frontend.dashboard.tenant.title",
  clients: "frontend.clients.section_title",
  catalog: "frontend.catalog.section_title",
  subscriptions: "frontend.subscriptions.title",
  settings: "frontend.settings.section_title",
  profile: "frontend.dashboard.client.profile",
  password: "frontend.dashboard.client.change_password",
  help: "frontend.help.title",
};

function moduleLabel(module: string, audience: HelpAudience): string {
  if (audience === "client" && module === "dashboard") {
    return t("frontend.dashboard.client.title");
  }
  const key = HELP_MODULE_LABEL_KEYS[module as HelpModule];
  return key ? t(key) : module;
}

function TopicList({
  topics,
  selectedId,
  onSelect,
  audience,
}: {
  topics: HelpListItem[];
  selectedId: string | null;
  onSelect: (topicId: string) => void;
  audience: HelpAudience;
}) {
  if (topics.length === 0) {
    return <p className="px-3 py-4 text-sm text-muted-foreground">{t("frontend.help.no_results")}</p>;
  }

  const grouped = new Map<string, HelpListItem[]>();
  for (const topic of topics) {
    const group = grouped.get(topic.module) ?? [];
    group.push(topic);
    grouped.set(topic.module, group);
  }
  const moduleOrder =
    audience === "client" ? CLIENT_HELP_MODULE_ORDER : ADMIN_HELP_MODULE_ORDER;
  const modules = [
    ...moduleOrder.filter((module) => grouped.has(module)),
    ...Array.from(grouped.keys()).filter(
      (module) => !moduleOrder.includes(module as HelpModule),
    ),
  ];

  return (
    <div className="flex flex-col gap-4">
      {modules.map((module) => (
        <section key={module} aria-labelledby={`help-module-${module}`}>
          <h3
            id={`help-module-${module}`}
            className="px-3 pb-1 text-xs font-semibold uppercase tracking-wide text-muted-foreground"
          >
            {moduleLabel(module, audience)}
          </h3>
          <div className="flex flex-col gap-1">
            {(grouped.get(module) ?? [])
              .slice()
              .sort((left, right) => left.order - right.order)
              .map((topic) => (
                <Button
                  key={topic.id}
                  variant={selectedId === topic.id ? "secondary" : "ghost"}
                  className="h-auto justify-start whitespace-normal px-3 py-2 text-left"
                  aria-current={selectedId === topic.id ? "page" : undefined}
                  onClick={() => onSelect(topic.id)}
                >
                  <span className="flex flex-col items-start gap-0.5">
                    <span>{topic.title}</span>
                    <span className="text-xs font-normal text-muted-foreground">
                      {"excerpt" in topic ? topic.excerpt : topic.summary}
                    </span>
                  </span>
                </Button>
              ))}
          </div>
        </section>
      ))}
    </div>
  );
}

function safeNavigationLabel(
  destination: ReturnType<typeof resolveSafeHelpNavigation>,
  audience: HelpAudience,
): string {
  if (!destination) {
    return "";
  }

  const moduleKey =
    destination.to === "/admin/dashboard"
      ? "frontend.dashboard.tenant.title"
      : destination.to === "/admin/clients"
        ? "frontend.clients.section_title"
        : destination.to === "/admin/catalog"
          ? "frontend.catalog.section_title"
          : destination.to === "/admin/subscriptions"
            ? "frontend.subscriptions.title"
            : destination.to === "/admin/settings"
              ? "frontend.settings.section_title"
              : destination.to === "/client/profile"
                ? "frontend.dashboard.client.profile"
                : destination.to === "/client/help"
                  ? "frontend.help.title"
                  : audience === "client"
                    ? "frontend.dashboard.client.title"
                    : "frontend.dashboard.tenant.title";
  const label = t(moduleKey);
  return `${t("frontend.help.go_to_module")}: ${label}`;
}

function SafeNavigationAnchor({
  navigation,
  audience,
}: {
  navigation: HelpTopic["safe_navigation"];
  audience: HelpAudience;
}) {
  const destination = resolveSafeHelpNavigation(navigation, audience);
  if (!destination) {
    return null;
  }

  const className = buttonVariants({ variant: "outline" });
  const label = safeNavigationLabel(destination, audience);
  if (destination.to === "/admin/settings") {
    return (
      <Link to={destination.to} search={destination.search} className={className}>
        {label}
      </Link>
    );
  }

  return (
    <Link to={destination.to} className={className}>
      {label}
    </Link>
  );
}

export function SafeNavigationLink({
  topic,
  audience = "tenant",
}: {
  topic: HelpTopic;
  audience?: HelpAudience;
}) {
  const navigations = [topic.safe_navigation, ...(topic.safe_links ?? [])];
  return (
    <div className="flex flex-wrap gap-2">
      {navigations.map((navigation, index) => (
        <SafeNavigationAnchor
          key={`${navigation.route}-${navigation.settings_category ?? "root"}-${index}`}
          navigation={navigation}
          audience={audience}
        />
      ))}
    </div>
  );
}

export function HelpCenterPage({
  audience = "tenant",
}: {
  audience?: HelpAudience;
}) {
  const { isAuthenticated, role } = useAuthStore();
  const expectedRole = audience === "client" ? "client" : "tenant";
  const [index, setIndex] = useState<HelpIndexResponse | null>(null);
  const [topic, setTopic] = useState<HelpTopic | null>(null);
  const [searchQuery, setSearchQuery] = useState("");
  const [searchResults, setSearchResults] = useState<HelpSearchResult[] | null>(null);
  const [searchError, setSearchError] = useState(false);
  const [mobileTopicsOpen, setMobileTopicsOpen] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);
  const searchRequestId = useRef(0);

  const loadTopic = useCallback(async (topicId: string) => {
    setError(false);
    try {
      setTopic(await getHelpTopic(topicId));
    } catch {
      setError(true);
    }
  }, []);

  const loadIndex = useCallback(async () => {
    searchRequestId.current += 1;
    setLoading(true);
    setError(false);
    setSearchError(false);
    setSearchQuery("");
    setSearchResults(null);
    try {
      const nextIndex = await getHelpIndex();
      setIndex(nextIndex);
      const firstTopic = nextIndex.topics[0];
      if (firstTopic) {
        await loadTopic(firstTopic.id);
      }
    } catch {
      setError(true);
    } finally {
      setLoading(false);
    }
  }, [loadTopic]);

  useEffect(() => {
    if (isPrivateHelpEnabled() && isAuthenticated && role === expectedRole) {
      void loadIndex();
    }
  }, [expectedRole, isAuthenticated, loadIndex, role]);

  async function handleSearch(value: string) {
    const requestId = ++searchRequestId.current;
    setSearchQuery(value);
    setSearchError(false);
    if (!value.trim()) {
      setSearchResults(null);
      setTopic(null);
      const firstTopic = index?.topics[0];
      if (firstTopic) {
        await loadTopic(firstTopic.id);
      }
      return;
    }

    setTopic(null);
    try {
      const response = await searchHelp(value);
      if (requestId === searchRequestId.current) {
        setSearchResults(response.results);
      }
    } catch {
      if (requestId === searchRequestId.current) {
        setSearchResults([]);
        setSearchError(true);
      }
    }
  }

  function selectTopic(topicId: string) {
    setMobileTopicsOpen(false);
    void loadTopic(topicId);
  }

  const topics = useMemo<HelpListItem[]>(
    () => searchResults ?? index?.topics ?? [],
    [index?.topics, searchResults],
  );
  const hasError = error || searchError;

  if (!isAuthenticated || role !== expectedRole) {
    return <Navigate to="/login" replace />;
  }

  if (!isPrivateHelpEnabled()) {
    return (
      <div className="mx-auto flex max-w-3xl flex-col gap-3 p-6" data-testid="help-disabled">
        <h1 className="font-heading text-2xl font-semibold">{t("frontend.help.title")}</h1>
        <p className="text-muted-foreground">{t("frontend.help.disabled")}</p>
      </div>
    );
  }

  return (
    <div className="mx-auto flex w-full max-w-7xl flex-col gap-5 p-4 sm:p-6 lg:p-8">
      <header className="flex flex-col gap-4">
        <div className="flex items-start justify-between gap-4">
          <div className="flex items-start gap-3">
            <span className="mt-1 flex size-10 items-center justify-center rounded-lg border bg-primary/8 text-primary">
              <BookOpen aria-hidden="true" />
            </span>
            <div>
              <h1 className="font-heading text-2xl font-semibold tracking-tight">{t("frontend.help.title")}</h1>
              <p className="text-muted-foreground">{t("frontend.help.subtitle")}</p>
            </div>
          </div>
          <Button
            variant="outline"
            className="md:hidden"
            aria-label={t("frontend.help.open_topics")}
            onClick={() => setMobileTopicsOpen(true)}
          >
            <Menu data-icon="inline-start" />
            {t("frontend.help.topics")}
          </Button>
        </div>
        <label className="relative block max-w-xl">
          <Search className="pointer-events-none absolute top-1/2 left-3 -translate-y-1/2 text-muted-foreground" aria-hidden="true" />
          <Input
            value={searchQuery}
            onChange={(event) => void handleSearch(event.target.value)}
            placeholder={t("frontend.help.search_placeholder")}
            aria-label={t("frontend.help.search")}
            className="h-10 pl-9 pr-9"
          />
          {searchQuery && (
            <Button
              type="button"
              variant="ghost"
              size="icon"
              className="absolute top-1/2 right-1 size-8 -translate-y-1/2"
              aria-label={t("frontend.help.clear_search")}
              onClick={() => void handleSearch("")}
            >
              <X aria-hidden="true" />
            </Button>
          )}
        </label>
      </header>

      {hasError && (
        <Alert variant="destructive">
          <AlertTitle>{t("frontend.help.error_title")}</AlertTitle>
          <AlertDescription className="flex items-center justify-between gap-3">
            {t("frontend.help.error_description")}
            <Button
              variant="outline"
              size="sm"
              onClick={() =>
                void (searchError ? handleSearch(searchQuery) : loadIndex())
              }
            >
              {t("frontend.help.retry")}
            </Button>
          </AlertDescription>
        </Alert>
      )}

      <div className="grid gap-6 md:grid-cols-[minmax(13rem,18rem)_minmax(0,1fr)]">
        <aside className="hidden md:block">
          <Card className="sticky top-6 shadow-none">
            <CardHeader><CardTitle className="text-base">{t("frontend.help.topics")}</CardTitle></CardHeader>
            <CardContent className="p-2 pt-0">
              {loading ? <Skeleton className="h-20 w-full" /> : <TopicList topics={topics} selectedId={topic?.id ?? null} onSelect={selectTopic} audience={audience} />}
            </CardContent>
          </Card>
        </aside>

        <main aria-live="polite" className="min-w-0">
          {loading && <Skeleton className="h-80 w-full rounded-xl" />}
          {!loading && topic && (
            <article className="flex flex-col gap-6">
              <div className="flex flex-wrap items-center gap-2">
                <Badge variant="secondary">{moduleLabel(topic.module, audience)}</Badge>
              </div>
              <SafeMarkdown source={topic.body} />
              <div>
                <SafeNavigationLink topic={topic} audience={audience} />
              </div>
            </article>
          )}
          {!loading && !topic && !hasError && (
            <p className="text-muted-foreground">
              {searchResults && searchResults.length > 0
                ? t("frontend.help.select_topic")
                : t("frontend.help.no_results")}
            </p>
          )}
        </main>
      </div>

      <Sheet open={mobileTopicsOpen} onOpenChange={setMobileTopicsOpen}>
        <SheetContent side="left" className="w-[min(90vw,24rem)]">
          <SheetHeader>
            <SheetTitle>{t("frontend.help.topics")}</SheetTitle>
          </SheetHeader>
          <div className="overflow-y-auto px-2 pb-4">
            <TopicList topics={topics} selectedId={topic?.id ?? null} onSelect={selectTopic} audience={audience} />
          </div>
        </SheetContent>
      </Sheet>
    </div>
  );
}
