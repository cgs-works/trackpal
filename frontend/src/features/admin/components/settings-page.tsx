import { useCallback, useEffect, useState } from "react";
import { Ban, Bell, Clock, Globe, KeyRound, Lock, Mail, MessageCircle, Shield, User } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Sheet, SheetContent, SheetHeader, SheetTitle, SheetTrigger } from "@/components/ui/sheet";
import { cn } from "@/lib/utils";
import { t } from "@/i18n";
import { useAuthStore } from "@/store/auth";
import { AccessControlSection } from "../components/access-control-section";
import { CodeServicesSection } from "../components/code-services-section";
import { LocaleSection } from "../components/locale-section";
import { MailboxSection } from "../components/mailbox-section";
import { PasswordSection } from "../components/password-section";
import { ProfileSection } from "../components/profile-section";
import { PublicApiSection } from "../components/public-api-section";
import { ReminderSettingsSection } from "../components/reminder-settings-section";
import { TimezoneSection } from "../components/timezone-section";
import { getProfile, type Profile } from "../services/settings-api";
import { WhatsappLinkSection } from "../components/whatsapp-link-section";

type SectionId = "reminders" | "locale" | "timezone" | "public-api" | "code-services" | "mailbox" | "access-control" | "profile" | "password" | "whatsapp-link";

type SettingsSection = {
  id: SectionId;
  title: string;
  description: string;
  icon: typeof Bell;
};

function buildSections(showProSettings: boolean): SettingsSection[] {
  return [
    ...(showProSettings ? [{ id: "reminders" as const, title: t("frontend.subscriptions.reminder_settings_title"), description: t("frontend.subscriptions.reminders_desc"), icon: Bell }] : []),
    { id: "locale", title: t("frontend.profile.language"), description: t("frontend.profile.language"), icon: Globe },
    ...(showProSettings ? [{ id: "timezone" as const, title: t("frontend.subscriptions.timezone"), description: t("frontend.subscriptions.timezone_description"), icon: Clock }] : []),
    ...(showProSettings ? [{ id: "public-api" as const, title: t("frontend.public_api.section_title"), description: t("frontend.public_api.description"), icon: KeyRound }] : []),
        ...(showProSettings ? [{ id: "whatsapp-link" as const, title: t("frontend.whatsapp_link.section_title"), description: t("frontend.whatsapp_link.section_description"), icon: MessageCircle }] : []),
    { id: "code-services", title: t("frontend.code_services.tenant_section_title"), description: t("frontend.code_services.product_description"), icon: Shield },
    { id: "mailbox", title: t("frontend.mailbox.section_title"), description: t("frontend.mailbox.section_heading"), icon: Mail },
    { id: "access-control", title: t("frontend.access_control.section_title"), description: t("frontend.access_control.section_description"), icon: Ban },
    { id: "profile", title: t("frontend.profile.section_title"), description: t("frontend.profile.section_heading"), icon: User },
    { id: "password", title: t("frontend.dashboard.client.change_password"), description: t("frontend.dashboard.client.change_password"), icon: Lock },
  ];
}

function CategoryList({ sections, activeSection, onSelect }: { sections: SettingsSection[]; activeSection: SectionId | null; onSelect: (sectionId: SectionId) => void }) {
  return (
    <nav aria-label={t("frontend.settings.select_category")} className="flex flex-col gap-2">
      {sections.map((section) => {
        const Icon = section.icon;
        const active = activeSection === section.id;
        return (
          <button
            key={section.id}
            type="button"
            aria-current={active ? "page" : undefined}
            onClick={() => onSelect(section.id)}
            className={cn(
              "flex w-full items-start gap-3 rounded-lg border px-3 py-3 text-left transition-colors hover:bg-accent focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
              active ? "border-primary bg-primary/5" : "border-transparent bg-background",
            )}
          >
            <Icon className="mt-0.5 size-5 shrink-0 text-muted-foreground" />
            <span className="flex min-w-0 flex-col gap-1">
              <span className="text-sm font-medium leading-none">{section.title}</span>
              <span className="line-clamp-2 text-xs text-muted-foreground">{section.description}</span>
            </span>
          </button>
        );
      })}
    </nav>
  );
}

export function SettingsPage() {
  const { role, tenantPlan, isMasterSupportContext } = useAuthStore();
  const isStarterTenantAdmin = role === "tenant" && tenantPlan === "starter";
  const showProSettings = !isStarterTenantAdmin || isMasterSupportContext;
  const sections = buildSections(showProSettings);
  const [activeSection, setActiveSection] = useState<SectionId | null>(null);
  const [categoryDrawerOpen, setCategoryDrawerOpen] = useState(false);
  const [profile, setProfile] = useState<Profile | null>(null);
  const [profileError, setProfileError] = useState<string | null>(null);
  const activeConfig = sections.find((section) => section.id === activeSection) ?? null;

  const loadProfile = useCallback(async () => {
    try {
      const data = await getProfile();
      setProfile(data);
      setProfileError(null);
    } catch {
      setProfileError(t("frontend.profile.error_update"));
    }
  }, []);

  useEffect(() => {
    loadProfile();
  }, [loadProfile]);

  function selectSection(sectionId: SectionId) {
    setActiveSection(sectionId);
    setCategoryDrawerOpen(false);
  }

  function renderSection(sectionId: SectionId) {
    switch (sectionId) {
      case "reminders":
        return <ReminderSettingsSection />;
      case "locale":
        return <LocaleSection />;
      case "timezone":
        return <TimezoneSection />;
      case "profile":
        if (profileError) {
          return (
            <div className="flex flex-col items-center gap-4 py-8 text-center">
              <p className="text-sm text-muted-foreground">{profileError}</p>
              <Button type="button" variant="outline" onClick={() => { setProfileError(null); loadProfile(); }}>
                {t("frontend.common.save")}
              </Button>
            </div>
          );
        }
        return profile ? <ProfileSection profile={profile} onProfileUpdate={setProfile} /> : null;
      case "password":
        return <PasswordSection />;
      case "mailbox":
        return <MailboxSection />;
      case "access-control":
        return <AccessControlSection />;
      case "code-services":
        return <CodeServicesSection />;
      case "public-api":
        return <PublicApiSection />;
          case "whatsapp-link":
            return <WhatsappLinkSection />;
    }
  }

  return (
    <div className="flex-1 p-4 md:p-6">
      <div className="mx-auto flex max-w-7xl flex-col gap-6">
        <div className="flex flex-col gap-4 md:flex-row md:items-end md:justify-between">
          <div>
            <h1 className="text-2xl font-bold tracking-tight">{t("frontend.settings.title")}</h1>
            <p className="text-muted-foreground">{t("frontend.settings.description")}</p>
          </div>
          <Sheet open={categoryDrawerOpen} onOpenChange={setCategoryDrawerOpen}>
            <SheetTrigger
              render={
                <Button type="button" variant="outline" className="md:hidden">
                  {activeConfig?.title ?? t("frontend.settings.select_category")}
                </Button>
              }
            />
            <SheetContent side="bottom" className="max-h-[85vh] overflow-y-auto">
              <SheetHeader>
                <SheetTitle>{t("frontend.settings.select_category")}</SheetTitle>
              </SheetHeader>
              <div className="mt-4">
                <CategoryList sections={sections} activeSection={activeSection} onSelect={selectSection} />
              </div>
            </SheetContent>
          </Sheet>
        </div>

        <div className="grid gap-6 md:grid-cols-[18rem_minmax(0,1fr)]">
          <aside className="hidden md:block">
            <Card className="sticky top-6">
              <CardContent className="p-3">
                <CategoryList sections={sections} activeSection={activeSection} onSelect={selectSection} />
              </CardContent>
            </Card>
          </aside>

          <Card className="min-h-[32rem] overflow-hidden" aria-label={t("frontend.settings.active_panel")}>
            {activeConfig ? (
              <>
                <CardHeader className="border-b">
                  <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
                    <div>
                      <CardTitle>{activeConfig.title}</CardTitle>
                      <CardDescription>{activeConfig.description}</CardDescription>
                    </div>
                    <Button type="button" variant="outline" onClick={() => setActiveSection(null)}>
                      {t("frontend.settings.cancel")}
                    </Button>
                  </div>
                </CardHeader>
                <CardContent className="max-h-[calc(100dvh-16rem)] overflow-y-auto p-4 md:p-6">
                  {renderSection(activeConfig.id)}
                </CardContent>
              </>
            ) : (
              <CardContent className="flex min-h-[32rem] items-center justify-center p-6 text-center">
                <div className="mx-auto flex max-w-md flex-col gap-2">
                  <h2 className="text-lg font-semibold">{t("frontend.settings.guide_title")}</h2>
                  <p className="text-sm text-muted-foreground">{t("frontend.settings.guide_description")}</p>
                </div>
              </CardContent>
            )}
          </Card>
        </div>
      </div>
    </div>
  );
}
