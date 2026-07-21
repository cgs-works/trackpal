import { useCallback, useEffect, useMemo, useState } from "react";
import { Link, Navigate } from "@tanstack/react-router";
import { BookOpen, Menu, Search } from "lucide-react";
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
  type HelpTopic,
  type HelpTopicSummary,
} from "../services/help-api";
import { SafeMarkdown } from "./safe-markdown";

function TopicList({
  topics,
  selectedId,
  onSelect,
}: {
  topics: HelpTopicSummary[];
  selectedId: string | null;
  onSelect: (topicId: string) => void;
}) {
  if (topics.length === 0) {
    return <p className="px-3 py-4 text-sm text-muted-foreground">{t("frontend.help.no_results")}</p>;
  }

  return (
    <div className="flex flex-col gap-1">
      {topics.map((topic) => (
        <Button
          key={topic.id}
          variant={selectedId === topic.id ? "secondary" : "ghost"}
          className="h-auto justify-start whitespace-normal px-3 py-2 text-left"
          aria-current={selectedId === topic.id ? "page" : undefined}
          onClick={() => onSelect(topic.id)}
        >
          <span className="flex flex-col items-start gap-0.5">
            <span>{topic.title}</span>
            <span className="text-xs font-normal text-muted-foreground">{topic.summary}</span>
          </span>
        </Button>
      ))}
    </div>
  );
}

export function HelpCenterPage() {
  const { isAuthenticated, role } = useAuthStore();
  const [index, setIndex] = useState<HelpIndexResponse | null>(null);
  const [topic, setTopic] = useState<HelpTopic | null>(null);
  const [searchQuery, setSearchQuery] = useState("");
  const [searchResults, setSearchResults] = useState<HelpTopicSummary[] | null>(null);
  const [mobileTopicsOpen, setMobileTopicsOpen] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);

  const loadTopic = useCallback(async (topicId: string) => {
    setError(false);
    try {
      setTopic(await getHelpTopic(topicId));
    } catch {
      setError(true);
    }
  }, []);

  const loadIndex = useCallback(async () => {
    setLoading(true);
    setError(false);
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
    if (isPrivateHelpEnabled() && isAuthenticated && role === "tenant") {
      void loadIndex();
    }
  }, [isAuthenticated, loadIndex, role]);

  async function handleSearch(value: string) {
    setSearchQuery(value);
    if (!value.trim()) {
      setSearchResults(null);
      return;
    }
    try {
      const response = await searchHelp(value);
      setSearchResults(response.results);
    } catch {
      setSearchResults([]);
    }
  }

  function selectTopic(topicId: string) {
    setMobileTopicsOpen(false);
    void loadTopic(topicId);
  }

  const topics = useMemo(
    () => searchResults ?? index?.topics ?? [],
    [index?.topics, searchResults],
  );

  if (!isAuthenticated || role !== "tenant") {
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
            className="h-10 pl-9"
          />
        </label>
      </header>

      {error && (
        <Alert variant="destructive">
          <AlertTitle>{t("frontend.help.error_title")}</AlertTitle>
          <AlertDescription className="flex items-center justify-between gap-3">
            {t("frontend.help.error_description")}
            <Button variant="outline" size="sm" onClick={() => void loadIndex()}>
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
              {loading ? <Skeleton className="h-20 w-full" /> : <TopicList topics={topics} selectedId={topic?.id ?? null} onSelect={selectTopic} />}
            </CardContent>
          </Card>
        </aside>

        <main aria-live="polite" className="min-w-0">
          {loading && <Skeleton className="h-80 w-full rounded-xl" />}
          {!loading && topic && (
            <article className="flex flex-col gap-6">
              <div className="flex flex-wrap items-center gap-2">
                <Badge variant="secondary">{t("frontend.dashboard.tenant.title")}</Badge>
              </div>
              <SafeMarkdown source={topic.body} />
              <div>
                <Link
                  to="/admin/dashboard"
                  className={buttonVariants({ variant: "outline" })}
                >
                  {t("frontend.help.go_to_module")}
                </Link>
              </div>
            </article>
          )}
          {!loading && !topic && !error && <p className="text-muted-foreground">{t("frontend.help.no_results")}</p>}
        </main>
      </div>

      <Sheet open={mobileTopicsOpen} onOpenChange={setMobileTopicsOpen}>
        <SheetContent side="left" className="w-[min(90vw,24rem)]">
          <SheetHeader>
            <SheetTitle>{t("frontend.help.topics")}</SheetTitle>
          </SheetHeader>
          <div className="overflow-y-auto px-2 pb-4">
            <TopicList topics={topics} selectedId={topic?.id ?? null} onSelect={selectTopic} />
          </div>
        </SheetContent>
      </Sheet>
    </div>
  );
}
