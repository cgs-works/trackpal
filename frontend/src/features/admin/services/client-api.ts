import api from "@/lib/api";

export interface Client {
  id: string;
  tenant_id: string;
  owner_user_id: string;
  full_name: string;
  username: string;
  phone: string | null;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

export interface ClientCreate {
  full_name: string;
  local_username: string;
  phone?: string;
  password: string;
}

export interface ClientUpdate {
  full_name?: string;
  local_username?: string;
  phone?: string;
}

export async function listClients(): Promise<Client[]> {
  const { data } = await api.get("/clients");
  return data;
}

export async function createClient(payload: ClientCreate): Promise<Client> {
  const { data } = await api.post("/clients", payload);
  return data;
}

export async function updateClient(
  id: string,
  payload: ClientUpdate
): Promise<Client> {
  const { data } = await api.put(`/clients/${id}`, payload);
  return data;
}

export async function deactivateClient(id: string): Promise<Client> {
  const { data } = await api.patch(`/clients/${id}/deactivate`);
  return data;
}

export async function activateClient(id: string): Promise<Client> {
  const { data } = await api.patch(`/clients/${id}/activate`);
  return data;
}

export async function deleteClient(id: string): Promise<void> {
  await api.delete(`/clients/${id}`);
}
