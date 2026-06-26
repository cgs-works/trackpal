import { useState, useEffect, useCallback } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Ban, Bell, Globe, Clock, Mail, Shield, User, Lock } from "lucide-react";
import { t } from "@/i18n";
import { useAuthStore } from "@/store/auth";
import { ReminderSettingsModal } from "../components/reminder-settings-modal";
import { ProfileSection } from "../components/profile-section";
import { PasswordSection } from "../components/password-section";
import { MailboxSection } from "../components/mailbox-section";
import { CodeServicesSection } from "../components/code-services-section";
import { AccessControlSection } from "../components/access-control-section";
import { LocaleSection } from "../components/locale-section";
import { TimezoneSection } from "../components/timezone-section";
import { getProfile, type Profile } from "../services/settings-api";

export function SettingsPage() {
  const { role, tenantPlan, isMasterSupportContext } = useAuthStore();
  const isStarterTenantAdmin = role === "tenant" && tenantPlan === "starter";
  const showProSettings = !isStarterTenantAdmin || isMasterSupportContext;

  const SECTIONS = [
    ...(showProSettings ? [{ id: "reminders" as const, title: t("frontend.subscriptions.reminder_settings_title"), description: t("frontend.subscriptions.reminders_desc"), icon: Bell }] : []),
    { id: "locale" as const, title: t("frontend.profile.language"), description: t("frontend.profile.language"), icon: Globe },
    ...(showProSettings ? [{ id: "timezone" as const, title: t("frontend.subscriptions.timezone"), description: t("frontend.subscriptions.timezone_description"), icon: Clock }] : []),
    { id: "code-services" as const, title: t("frontend.code_services.tenant_section_title"), description: t("frontend.code_services.product_description"), icon: Shield },
    { id: "mailbox" as const, title: t("frontend.mailbox.section_title"), description: t("frontend.mailbox.section_heading"), icon: Mail },
    { id: "access-control" as const, title: t("frontend.access_control.section_title"), description: t("frontend.access_control.section_description"), icon: Ban },
    { id: "profile" as const, title: t("frontend.profile.section_title"), description: t("frontend.profile.section_heading"), icon: User },
    { id: "password" as const, title: t("frontend.dashboard.client.change_password"), description: t("frontend.dashboard.client.change_password"), icon: Lock },
  ];

  type SectionId = (typeof SECTIONS)[number]["id"];
  const [openSection, setOpenSection] = useState<SectionId | null>(null);
  const [reminderModalOpen, setReminderModalOpen] = useState(false);
  const [profile, setProfile] = useState<Profile | null>(null);

  const loadProfile = useCallback(async () => {
    try {
      const data = await getProfile();
      setProfile(data);
    } catch {
      // Non-critical
    }
  }, []);

  useEffect(() => {
    loadProfile();
  }, [loadProfile]);

  function handleToggle(sectionId: SectionId) {
    if (sectionId === "reminders") {
      setReminderModalOpen(true);
      return;
    }
    setOpenSection((prev) => (prev === sectionId ? null : sectionId));
  }

  function renderSection(sectionId: SectionId) {
    switch (sectionId) {
      case "locale":
        return <LocaleSection />;
      case "timezone":
        return <TimezoneSection />;
      case "profile":
        return profile ? <ProfileSection profile={profile} onProfileUpdate={setProfile} /> : null;
      case "password":
        return <PasswordSection />;
      case "mailbox":
        return <MailboxSection />;
      case "access-control":
        return <AccessControlSection />;
      case "code-services":
        return <CodeServicesSection />;
      case "reminders":
        return null;
    }
  }

  return (
    <div className="flex-1 p-6">
      <div className="max-w-4xl mx-auto space-y-6">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">{t("frontend.settings.title")}</h1>
          <p className="text-muted-foreground">
            {t("frontend.settings.description")}
          </p>
        </div>

        <div className="grid gap-4">
          {SECTIONS.map((section) => {
            const isOpen = openSection === section.id;
            const Icon = section.icon;
            return (
              <Card key={section.id}>
                <CardHeader
                  className="flex flex-row items-center justify-between space-y-0 pb-2 cursor-pointer select-none"
                  onClick={() => handleToggle(section.id)}
                >
                  <CardTitle className="flex items-center gap-2 text-base">
                    <Icon className="size-5 text-muted-foreground" />
                    {section.title}
                  </CardTitle>
                  <Button variant="outline" size="sm">
                    {isOpen ? t("frontend.settings.close") : t("frontend.settings.configure")}
                  </Button>
                </CardHeader>
                <CardContent>
                  <p className="text-sm text-muted-foreground">
                    {section.description}
                  </p>

                  {isOpen && (
                    <div className="mt-4">
                      {renderSection(section.id)}
                    </div>
                  )}
                </CardContent>
              </Card>
            );
          })}
        </div>
      </div>

      <ReminderSettingsModal
        open={reminderModalOpen}
        onOpenChange={setReminderModalOpen}
      />
    </div>
  );
}
