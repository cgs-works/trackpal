export interface Tenant {
  id: string
  full_name: string
  client_prefix: string
  email: string | null
  phone: string | null
  evolution_instance_name: string | null
  is_active: boolean
  username: string
  created_at: string
}

export interface TenantMeta {
  total: number
  active: number
  inactive: number
}

export interface TenantListResponse {
  data: Tenant[]
  meta: TenantMeta
}
