import { useState, useEffect, useCallback } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Bell, Mail, Shield, User, Lock } from "lucide-react";
import { ReminderSettingsModal } from "../components/reminder-settings-modal";
import { ProfileSection } from "../components/profile-section";
import { PasswordSection } from "../components/password-section";
import { MailboxSection } from "../components/mailbox-section";
import { CodeServicesSection } from "../components/code-services-section";
import { getProfile, type Profile } from "../services/settings-api";

const SECTIONS = [
  { id: "reminders", title: "Subscription Reminders", description: "Configure WhatsApp reminder messages for expiring subscriptions", icon: Bell },
  { id: "code-services", title: "Code Services", description: "Manage code services for your business", icon: Shield },
  { id: "mailbox", title: "Mailbox", description: "Connect your email for subscription notifications", icon: Mail },
  { id: "profile", title: "Profile", description: "Update your personal information", icon: User },
  { id: "password", title: "Password", description: "Change your account password", icon: Lock },
] as const;

type SectionId = (typeof SECTIONS)[number]["id"];

export function SettingsPage() {
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

  return (
    <div className="flex-1 p-6">
      <div className="max-w-4xl mx-auto space-y-6">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">Settings</h1>
          <p className="text-muted-foreground">
            Manage your account and notification preferences
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
                    {isOpen ? "Close" : "Configure"}
                  </Button>
                </CardHeader>
                <CardContent>
                  <p className="text-sm text-muted-foreground">
                    {section.description}
                  </p>

                  {/* Expanded sections */}
                  {section.id === "profile" && isOpen && profile && (
                    <div className="mt-4">
                      <ProfileSection
                        profile={profile}
                        onProfileUpdate={setProfile}
                      />
                    </div>
                  )}
                  {section.id === "password" && isOpen && (
                    <div className="mt-4">
                      <PasswordSection />
                    </div>
                  )}
                  {section.id === "mailbox" && isOpen && (
                    <div className="mt-4">
                      <MailboxSection />
                    </div>
                  )}
                  {section.id === "code-services" && isOpen && (
                    <div className="mt-4">
                      <CodeServicesSection />
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
