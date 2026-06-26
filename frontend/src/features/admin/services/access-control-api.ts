import api from "@/lib/api";

export interface AccessControlBlock {
  id: string;
  tenant_id: string;
  phone: string | null;
  whatsapp_lid: string | null;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

export async function listAccessBlocks(): Promise<AccessControlBlock[]> {
  const { data } = await api.get("/access-control/blocks");
  return data;
}

export async function createAccessBlock(phone: string): Promise<AccessControlBlock> {
  const { data } = await api.post("/access-control/blocks", { phone });
  return data;
}

export async function deleteAccessBlock(id: string): Promise<void> {
  await api.delete(`/access-control/blocks/${id}`);
}
