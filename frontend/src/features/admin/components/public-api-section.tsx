import { useCallback, useEffect, useMemo, useState } from "react";
import { toast } from "sonner";
import { Copy, Eye, EyeOff, KeyRound, Plus, Trash2 } from "lucide-react";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Skeleton } from "@/components/ui/skeleton";
import { t } from "@/i18n";
import { getApiError } from "@/lib/api-errors";
import { useAuthStore } from "@/store/auth";
import { useSettingsStore } from "@/store/settings";
import { DemoPublicApiCard } from "./demo-public-api-card";

const LANGUAGES = ["html", "react", "vue", "svelte", "angular", "alpine"] as const;
const API_KEY_PLACEHOLDER = "YOUR_PUBLIC_API_KEY";
const TOOLTIP = "frontend.public_api.tooltip";

type Language = (typeof LANGUAGES)[number];

function maskKey(key: string): string {
  return `${key.slice(0, 4)}••••••••••••••••••`;
}

function isUrlish(value: string): boolean {
  return /^https?:\/\/[^\s/$.?#].[^\s]*$/i.test(value.trim());
}

function unique(items: string[]): string[] {
  return Array.from(new Set(items.map((item) => item.trim()).filter(Boolean)));
}

export function PublicApiSection() {
  const { dataSource } = useAuthStore();
  const isDemo = dataSource.mode === "demo";
  const { publicApiKey, publicApiKeyLoaded, loadPublicApiKey, savePublicApiKeyOrigins, revokePublicApiKey } = useSettingsStore();
  const [origins, setOrigins] = useState<string[]>([]);
  const [originInput, setOriginInput] = useState("");
  const [showKey, setShowKey] = useState(false);
  const [language, setLanguage] = useState<Language>("html");
  const [loading, setLoading] = useState(!publicApiKeyLoaded && !isDemo);
  const [saving, setSaving] = useState(false);
  const [revoking, setRevoking] = useState(false);

  const load = useCallback(async () => {
    if (isDemo) {
      setOrigins([]);
      setLoading(false);
      return;
    }
    if (publicApiKeyLoaded) {
      setOrigins(publicApiKey?.allowed_origins ?? []);
      setLoading(false);
      return;
    }
    setLoading(true);
    try {
      const config = await loadPublicApiKey();
      setOrigins(config?.allowed_origins ?? []);
    } catch (error) {
      toast.error(getApiError(error, t("frontend.public_api.error_load")));
    } finally {
      setLoading(false);
    }
  }, [isDemo, loadPublicApiKey, publicApiKey, publicApiKeyLoaded]);

  useEffect(() => {
    load();
  }, [load]);

  const baseUrl = import.meta.env.VITE_API_URL || "http://localhost:8000/api/v1";
  const example = useMemo(() => buildExample(language, baseUrl), [baseUrl, language]);

  async function save(nextOrigins = origins) {
    setSaving(true);
    try {
      const config = await savePublicApiKeyOrigins(unique(nextOrigins));
      setOrigins(config.allowed_origins);
      setOriginInput("");
      toast.success(t("frontend.public_api.saved"));
    } catch (error) {
      toast.error(getApiError(error, t("frontend.public_api.error_save")));
    } finally {
      setSaving(false);
    }
  }

  async function handleCreate(event: React.FormEvent) {
    event.preventDefault();
    if (!isUrlish(originInput)) return;
    await save([originInput]);
  }

  function handleAddSite() {
    if (!isUrlish(originInput)) return;
    setOrigins((items) => unique([...items, originInput]));
    setOriginInput("");
  }

  async function handleRevoke() {
    setRevoking(true);
    try {
      await revokePublicApiKey();
      setOrigins([]);
      setOriginInput("");
      setShowKey(false);
      toast.success(t("frontend.public_api.revoked"));
    } catch (error) {
      toast.error(getApiError(error, t("frontend.public_api.error_revoke")));
    } finally {
      setRevoking(false);
    }
  }

  async function handleCopy() {
    if (!publicApiKey?.api_key) return;
    try {
      await navigator.clipboard.writeText(publicApiKey.api_key);
      toast.success(t("frontend.public_api.copied"));
    } catch (error) {
      toast.error(getApiError(error, t("frontend.public_api.error_load")));
    }
  }

  async function handleCopyHandoff() {
    try {
      await navigator.clipboard.writeText(buildDeveloperHandoffPackage(baseUrl, origins));
      toast.success(t("frontend.public_api.handoff_copied"));
    } catch (error) {
      toast.error(getApiError(error, t("frontend.public_api.error_load")));
    }
  }

  if (loading) {
    return (
      <div className="flex flex-col gap-3">
        <Skeleton className="h-9 w-full" />
        <Skeleton className="h-24 w-full" />
      </div>
    );
  }

  if (isDemo) {
    return <DemoPublicApiCard />;
  }

  const props = {
    publicApiKey,
    origins,
    originInput,
    showKey,
    language,
    example,
    saving,
    revoking,
    setOriginInput,
    setOrigins,
    setShowKey,
    setLanguage,
    handleAddSite,
    handleCopy,
    handleCopyHandoff,
    handleCreate,
    handleRevoke,
    save,
  };

  return <GuidedLayout {...props} />;
}

type VariantProps = {
  publicApiKey: ReturnType<typeof useSettingsStore.getState>["publicApiKey"];
  origins: string[];
  originInput: string;
  showKey: boolean;
  language: Language;
  example: string;
  saving: boolean;
  revoking: boolean;
  setOriginInput: (value: string) => void;
  setOrigins: React.Dispatch<React.SetStateAction<string[]>>;
  setShowKey: (value: boolean) => void;
  setLanguage: (value: Language) => void;
  handleAddSite: () => void;
  handleCopy: () => void;
  handleCopyHandoff: () => Promise<void>;
  handleCreate: (event: React.FormEvent) => void;
  handleRevoke: () => void;
  save: () => Promise<void>;
};

function GuidedLayout(props: VariantProps) {
  return (
    <div className="flex flex-col gap-4 rounded-xl border bg-card p-4">
      <Header />
      {!props.publicApiKey ? <CreateKeyCard {...props} /> : <KeyCard {...props} />}
      {props.publicApiKey && <SitesEditor {...props} />}
      {props.publicApiKey && <DeveloperTabs {...props} />}
      {props.publicApiKey && <DangerZone {...props} />}
    </div>
  );
}

function Header() {
  return (
    <div className="flex flex-col gap-1">
      <div className="flex items-center gap-2">
        <h2 className="text-base font-medium">{t("frontend.public_api.section_title")}</h2>
        <span title={t(TOOLTIP)} className="inline-flex size-5 items-center justify-center rounded-full border text-xs text-muted-foreground">?</span>
        <Badge variant="secondary">{t("frontend.public_api.read_only")}</Badge>
      </div>
      <p className="text-sm text-muted-foreground">{t("frontend.public_api.description")}</p>
    </div>
  );
}

function CreateKeyCard({ originInput, saving, setOriginInput, handleCreate }: VariantProps) {
  return (
    <form onSubmit={handleCreate} className="flex flex-col gap-3 rounded-lg border bg-background p-3">
      <div className="flex items-center gap-2">
        <KeyRound className="text-muted-foreground" data-icon="inline-start" />
        <p className="text-sm font-medium">{t("frontend.public_api.create_first_site")}</p>
      </div>
      <Label htmlFor="public-api-first-site">{t("frontend.public_api.site_label")}</Label>
      <div className="flex flex-col gap-2 sm:flex-row">
        <Input id="public-api-first-site" value={originInput} onChange={(event) => setOriginInput(event.target.value)} placeholder="https://tusitio.com" />
        <Button type="submit" disabled={saving || !isUrlish(originInput)}>{saving ? t("frontend.common.saving") : t("frontend.public_api.create_key")}</Button>
      </div>
    </form>
  );
}

function KeyCard({ publicApiKey, showKey, setShowKey, handleCopy }: VariantProps) {
  if (!publicApiKey) return null;
  return (
    <div className="flex flex-col gap-3 rounded-lg border bg-background p-3 sm:flex-row sm:items-center sm:justify-between">
      <div className="min-w-0">
        <Label>{t("frontend.public_api.key_label")}</Label>
        <code className="mt-1 block truncate rounded bg-muted px-2 py-1 text-xs">{showKey ? publicApiKey.api_key : maskKey(publicApiKey.api_key)}</code>
      </div>
      <div className="flex flex-wrap gap-2">
        <Button type="button" variant="outline" size="sm" onClick={() => setShowKey(!showKey)}>
          {showKey ? <EyeOff data-icon="inline-start" /> : <Eye data-icon="inline-start" />}
          {showKey ? t("frontend.public_api.hide") : t("frontend.public_api.show")}
        </Button>
        <Button type="button" variant="outline" size="sm" onClick={handleCopy}>
          <Copy data-icon="inline-start" />
          {t("frontend.public_api.copy")}
        </Button>
      </div>
    </div>
  );
}

function SitesEditor({ origins, originInput, saving, setOriginInput, setOrigins, handleAddSite, save }: VariantProps) {
  return (
    <div className="flex flex-col gap-3 rounded-lg border bg-background p-3">
      <div>
        <Label htmlFor="public-api-site">{t("frontend.public_api.sites_label")}</Label>
        <p className="text-xs text-muted-foreground">{t("frontend.public_api.sites_help")}</p>
      </div>
      <div className="flex flex-col gap-2 sm:flex-row">
        <Input id="public-api-site" value={originInput} onChange={(event) => setOriginInput(event.target.value)} placeholder="https://mitienda.com" />
        <Button type="button" variant="outline" onClick={handleAddSite} disabled={!isUrlish(originInput)}>
          <Plus data-icon="inline-start" />
          {t("frontend.public_api.add_site")}
        </Button>
      </div>
      <div className="flex flex-col gap-2">
        {origins.map((origin) => (
          <div key={origin} className="flex flex-col gap-2 rounded-md border p-2 sm:flex-row sm:items-center sm:justify-between">
            <code className="truncate text-xs">{origin}</code>
            <Button type="button" variant="ghost" size="sm" onClick={() => setOrigins((items) => items.filter((item) => item !== origin))}>
              <Trash2 data-icon="inline-start" />
              {t("frontend.public_api.delete_site")}
            </Button>
          </div>
        ))}
      </div>
      <Button type="button" className="self-start" disabled={saving || origins.length === 0} onClick={() => void save()}>
        {saving ? t("frontend.common.saving") : t("frontend.public_api.save_changes")}
      </Button>
    </div>
  );
}

function DeveloperTabs({ language, example, setLanguage, handleCopyHandoff }: VariantProps) {
  return (
    <div className="flex flex-col gap-3 rounded-lg border bg-background p-3">
      <div className="flex flex-col gap-2 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <Label>{t("frontend.public_api.developer_title")}</Label>
          <p className="text-xs text-muted-foreground">{t("frontend.public_api.browser_only_warning")}</p>
        </div>
        <Button type="button" variant="outline" size="sm" onClick={() => void handleCopyHandoff()}>
          <Copy data-icon="inline-start" />
          {t("frontend.public_api.copy_handoff")}
        </Button>
      </div>
      <div className="flex flex-wrap gap-2">
        {LANGUAGES.map((item) => (
          <Button key={item} type="button" variant={language === item ? "default" : "outline"} size="sm" onClick={() => setLanguage(item)}>
            {t(`frontend.public_api.lang_${item}`)}
          </Button>
        ))}
      </div>
      <code className="overflow-x-auto whitespace-pre rounded-lg bg-muted p-3 text-xs text-muted-foreground">{example}</code>
    </div>
  );
}

function DangerZone({ revoking, handleRevoke }: VariantProps) {
  const [open, setOpen] = useState(false);

  async function confirmDelete() {
    await handleRevoke();
    setOpen(false);
  }

  return (
    <div className="flex flex-col gap-3 rounded-lg border border-destructive/30 bg-background p-3">
      <Label>{t("frontend.public_api.danger_title")}</Label>
      <p className="text-xs text-muted-foreground">{t("frontend.public_api.delete_key_help")}</p>
      <Button type="button" variant="destructive" className="self-start" onClick={() => setOpen(true)}>
        <Trash2 data-icon="inline-start" />
        {t("frontend.public_api.delete_key")}
      </Button>
      <AlertDialog open={open} onOpenChange={setOpen}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>{t("frontend.public_api.delete_key_title")}</AlertDialogTitle>
            <AlertDialogDescription>{t("frontend.public_api.delete_key_description")}</AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>{t("frontend.common.cancel")}</AlertDialogCancel>
            <AlertDialogAction variant="destructive" disabled={revoking} onClick={() => void confirmDelete()}>
              {revoking ? t("frontend.common.deleting") : t("frontend.public_api.delete_key")}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
}

export function buildDeveloperHandoffPackage(baseUrl: string, origins: string[]): string {
  const originList = origins.length > 0 ? origins.join(", ") : t("frontend.public_api.handoff_no_origins");
  const examples = LANGUAGES.flatMap((language) => [
    t(`frontend.public_api.lang_${language}`),
    buildExample(language, baseUrl),
    "",
  ]);

  return [
    t("frontend.public_api.handoff_title"),
    t("frontend.public_api.handoff_instructions"),
    `${t("frontend.public_api.handoff_endpoint")}: ${baseUrl}/public/catalog`,
    `${t("frontend.public_api.handoff_origins")}: ${originList}`,
    `${t("frontend.public_api.handoff_key")}: ${API_KEY_PLACEHOLDER}`,
    "",
    ...examples,
  ].join("\n");
}

function buildExample(language: Language, baseUrl: string): string {
  const url = `${baseUrl}/public/catalog?api_key=${API_KEY_PLACEHOLDER}`;
  if (language === "react") return `useEffect(() => {\n  fetch("${url}")\n    .then((res) => res.json())\n    .then(setCatalog);\n}, []);`;
  if (language === "vue") return `<script setup>\nimport { onMounted, ref } from "vue";\n\nconst catalog = ref(null);\n\nonMounted(async () => {\n  catalog.value = await fetch("${url}").then((res) => res.json());\n});\n</script>`;
  if (language === "svelte") return `<script>\n  import { onMount } from "svelte";\n\n  let catalog;\n\n  onMount(async () => {\n    catalog = await fetch("${url}").then((res) => res.json());\n  });\n</script>`;
  if (language === "angular") return `import { HttpClient } from "@angular/common/http";\n\nconstructor(private http: HttpClient) {}\n\ncatalog$ = this.http.get("${url}");`;
  if (language === "alpine") return `<div x-data="{ catalog: null }"\n  x-init="catalog = await fetch('${url}').then((res) => res.json())">\n</div>`;
  return `<script>\nfetch("${url}")\n  .then((res) => res.json())\n  .then((catalog) => console.log(catalog));\n</script>`;
}
