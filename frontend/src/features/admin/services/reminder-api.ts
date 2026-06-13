import api from "@/lib/api";

export interface ReminderSettings {
  id: string;
  tenant_id: string;
  warning_days: number[];
  reminder_time: string;
  recipient_mode: "tenant_only" | "client_only" | "both";
  reminders_enabled: boolean;
  custom_message_tenant: string | null;
  custom_message_client: string | null;
  created_at: string;
  updated_at: string;
}

export interface ReminderSettingsUpdate {
  warning_days?: number[];
  reminder_time?: string;
  recipient_mode?: "tenant_only" | "client_only" | "both";
  reminders_enabled?: boolean;
  custom_message_tenant?: string | null;
  custom_message_client?: string | null;
}

export async function getReminderSettings(): Promise<ReminderSettings> {
  const { data } = await api.get("/subscription-settings");
  return data;
}

export async function updateReminderSettings(
  payload: ReminderSettingsUpdate
): Promise<ReminderSettings> {
  const { data } = await api.put("/subscription-settings", payload);
  return data;
}


