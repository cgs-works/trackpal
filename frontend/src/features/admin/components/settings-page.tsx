import { useState } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Bell, Mail, Shield, User } from "lucide-react";
import { ReminderSettingsModal } from "../components/reminder-settings-modal";

const SETTINGS_SECTIONS = [
  {
    id: "reminders",
    title: "Subscription Reminders",
    description: "Configure WhatsApp reminder messages for expiring subscriptions",
    icon: Bell,
  },
  {
    id: "mailbox",
    title: "Mailbox",
    description: "Connect your email for subscription notifications",
    icon: Mail,
    disabled: true,
  },
  {
    id: "code-services",
    title: "Code Services",
    description: "Manage code services for your business",
    icon: Shield,
    disabled: true,
  },
  {
    id: "profile",
    title: "Profile",
    description: "Update your personal information",
    icon: User,
    disabled: true,
  },
];

export function SettingsPage() {
  const [reminderModalOpen, setReminderModalOpen] = useState(false);

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
          {SETTINGS_SECTIONS.map((section) => (
            <Card
              key={section.id}
              className={section.disabled ? "opacity-60" : ""}
            >
              <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                <CardTitle className="flex items-center gap-2 text-base">
                  <section.icon className="size-5 text-muted-foreground" />
                  {section.title}
                </CardTitle>
                {!section.disabled && (
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => {
                      if (section.id === "reminders") {
                        setReminderModalOpen(true);
                      }
                    }}
                  >
                    Configure
                  </Button>
                )}
                {section.disabled && (
                  <span className="text-xs text-muted-foreground">
                    Coming soon
                  </span>
                )}
              </CardHeader>
              <CardContent>
                <p className="text-sm text-muted-foreground">
                  {section.description}
                </p>
              </CardContent>
            </Card>
          ))}
        </div>
      </div>

      <ReminderSettingsModal
        open={reminderModalOpen}
        onOpenChange={setReminderModalOpen}
      />
    </div>
  );
}
