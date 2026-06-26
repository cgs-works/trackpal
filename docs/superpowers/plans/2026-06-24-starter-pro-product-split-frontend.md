# Starter/Pro Product Split Frontend Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Render the correct web product surface for Starter, Pro, and Master-switched support contexts using backend `tenant_plan` as a stale-correcting UI hint.

**Architecture:** Backend remains the authorization source of truth; frontend only hides/shows routes and sections for usability. `authStore.tenantPlan` is loaded from auth responses and corrected by dashboard responses. Master with `activeTenantId` is a support context and sees the full admin UI plus a banner, even when the tenant is Starter.

**Tech Stack:** React 19, TypeScript strict, Zustand, TanStack Router file routes, Tailwind CSS v4, shadcn/ui primitives already installed, Axios.

## Global Constraints

- Frontend `tenant_plan` is only a UI hint and must never be trusted for backend authorization.
- Starter tenant admin sees a reduced product surface.
- Pro tenant admin sees the full product surface.
- Master switched into a Starter tenant bypasses plan gates and sees full UI with a support banner.
- Starter tenant direct access to Pro-only frontend routes shows 404.
- Dashboard common widgets for Starter/Pro: plan, mailbox status, enabled platform count/list, Control de acceso count.
- Pro dashboard adds active clients, catalog services, active subscriptions, and subscriptions expiring in the next 7 tenant-local calendar days.
- `timezone` remains physically in tenant settings but is hidden/blocked for tenant admin Starter.
- `locale` remains available to Starter.
- Visible UI labels exactly: **Plataformas habilitadas**, **Correo central de búsqueda**, **Control de acceso**.
- Control de acceso is available in Settings for Starter and Pro.
- No new frontend test framework; current frontend verification is `npm run build` and `npm run lint`.
- Use existing shadcn/ui components first; do not add dependencies.

---

## File Structure

### Create
- `frontend/src/features/admin/components/not-found-page.tsx` — lightweight frontend 404 for plan-hidden admin routes.
- `frontend/src/features/admin/components/plan-route-gate.tsx` — small route wrapper for Pro-only pages.
- `frontend/src/features/admin/components/support-banner.tsx` — banner shown for Master switched into Starter tenant.
- `frontend/src/features/admin/components/access-control-section.tsx` — Settings section to list/block/unblock phone blocks.
- `frontend/src/features/admin/services/access-control-api.ts` — typed REST calls for `/access-control/blocks`.
- `frontend/src/features/admin/services/dashboard-api.ts` — typed dashboard response call for tenant dashboard.

### Modify
- `frontend/src/features/auth/services/auth-api.ts` — add `tenant_plan` to auth response type.
- `frontend/src/store/auth.ts` — persist `tenantPlan`, expose support helpers, add stale correction action.
- `frontend/src/features/master/services/tenant-api.ts` — add tenant `plan` type.
- `frontend/src/features/master/components/business-form-dialog.tsx` — create/edit plan selector.
- `frontend/src/features/master/components/business-table.tsx` — Plan badge/column.
- `frontend/src/features/master/components/dashboard-page.tsx` — send plan on create/update, navigate to admin support context.
- `frontend/src/features/admin/layout/admin-layout.tsx` — plan-aware navigation and support banner.
- `frontend/src/routes/admin/clients.tsx`, `frontend/src/routes/admin/catalog.tsx`, `frontend/src/routes/admin/subscriptions.tsx` — wrap Pro-only routes.
- `frontend/src/features/admin/components/settings-page.tsx` — plan-aware sections and visible labels.
- `frontend/src/features/admin/components/mailbox-section.tsx` — visible name/help/description copy.
- `frontend/src/features/admin/components/code-services-section.tsx` — visible name/help/description copy.
- `frontend/src/features/admin/components/dashboard-page.tsx` — real dashboard widgets and stale plan correction.
- `frontend/src/features/admin/services/settings-api.ts` — allow `TenantSettings.timezone: string | null`.
- Backend i18n files in the backend plan supply new keys; frontend uses `t()` only.
- `docs/architecture/frontend-architecture.md`, `docs/codebase/frontend-components.md`, `docs/codebase/frontend-structure.md`, `docs/code-standard/frontend-conventions.md` — sync docs.

---

### Task 1: Auth store carries `tenant_plan` and support-context helpers

**Files:**
- Modify: `frontend/src/features/auth/services/auth-api.ts:3-15`
- Modify: `frontend/src/store/auth.ts:13-125`

**Interfaces:**
- Produces: `TenantPlan = "starter" | "pro"`.
- Produces: `AuthState.tenantPlan: TenantPlan | null`.
- Produces: `AuthState.isMasterSupportContext: boolean` derived as `role === "master" && activeTenantId !== null`.
- Produces: `AuthState.setTenantPlan(plan: TenantPlan | null): void` for dashboard stale correction.

- [ ] **Step 1: Update auth API types**

In `frontend/src/features/auth/services/auth-api.ts`, add:

```ts
export type TenantPlan = "starter" | "pro";
```

Update `TokenResponse`:

```ts
export interface TokenResponse {
  access_token: string
  refresh_token: string
  token_type: string
  user: UserInfo
  active_tenant_id: string | null
  tenant_plan: TenantPlan | null
}
```

- [ ] **Step 2: Update persisted auth state**

In `frontend/src/store/auth.ts`, import `TenantPlan`:

```ts
  type TenantPlan,
```

Update `AuthState`:

```ts
  tenantPlan: TenantPlan | null
  isMasterSupportContext: boolean
  setTenantPlan: (plan: TenantPlan | null) => void
```

Update `loadFromStorage()`:

```ts
    tenantPlan: localStorage.getItem("tenantPlan") as TenantPlan | null,
```

Update `saveTokenData()`:

```ts
  if (data.tenant_plan) {
    localStorage.setItem("tenantPlan", data.tenant_plan);
  } else {
    localStorage.removeItem("tenantPlan");
  }
```

Update `clearTokenData()`:

```ts
  localStorage.removeItem("tenantPlan");
```

Update initial state:

```ts
  tenantPlan: initial.tenantPlan,
  isMasterSupportContext: initial.user?.role === "master" && !!initial.activeTenantId,
```

Update `login()` set block:

```ts
      tenantPlan: data.tenant_plan,
      isMasterSupportContext: data.user.role === "master" && !!data.active_tenant_id,
```

Update `logout()` set block:

```ts
      tenantPlan: null,
      isMasterSupportContext: false,
```

Update `switchTenant()` set block:

```ts
      tenantPlan: data.tenant_plan,
      isMasterSupportContext: data.user.role === "master" && !!data.active_tenant_id,
```

Add action:

```ts
  setTenantPlan: (plan) => {
    if (plan) {
      localStorage.setItem("tenantPlan", plan);
    } else {
      localStorage.removeItem("tenantPlan");
    }
    set({ tenantPlan: plan });
  },
```

- [ ] **Step 3: Verify typecheck catches no drift**

Run:

```bash
cd frontend && npm run build
```

Expected: FAIL until backend-generated runtime exists is okay in dev, but TypeScript should compile once all references are correct. If it fails on missing `tenant_plan` in mocks, update only those mocks.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/features/auth/services/auth-api.ts frontend/src/store/auth.ts
git commit -m "feat: persist tenant plan in auth store"
```

---

### Task 2: Master can create/edit/list tenant plans

**Files:**
- Modify: `frontend/src/features/master/services/tenant-api.ts:3-13`
- Modify: `frontend/src/features/master/components/business-form-dialog.tsx:13-177`
- Modify: `frontend/src/features/master/components/business-table.tsx:1-163`
- Modify: `frontend/src/features/master/components/dashboard-page.tsx:105-218`

**Interfaces:**
- Consumes: backend `TenantResponse.plan` and `TenantCreate.plan`.
- Produces: Master create form requires `plan`.
- Produces: Master edit form includes `plan`; omitted plan is not used by UI because the user can see current plan and submit explicit value.

- [ ] **Step 1: Update tenant API type**

In `frontend/src/features/master/services/tenant-api.ts`, import type:

```ts
import type { TenantPlan } from "@/features/auth/services/auth-api";
```

Add to `Tenant`:

```ts
  plan: TenantPlan
```

- [ ] **Step 2: Add plan to form shape**

In `business-form-dialog.tsx`, import Select components:

```ts
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import type { TenantPlan } from "@/features/auth/services/auth-api";
```

Update `BusinessForm`:

```ts
  plan: TenantPlan
```

Update `getEmptyForm()`:

```ts
    plan: "starter",
```

Update prop type:

```ts
  onFormChange: (key: keyof BusinessForm, value: string) => void
```

Add this form field after Full Name:

```tsx
          <div className="flex flex-col gap-2">
            <Label htmlFor="tenant_plan">Plan</Label>
            <Select value={form.plan} onValueChange={(value) => onFormChange("plan", value)}>
              <SelectTrigger id="tenant_plan">
                <SelectValue placeholder="Select plan" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="starter">Starter</SelectItem>
                <SelectItem value="pro">Pro</SelectItem>
              </SelectContent>
            </Select>
            <p className="text-xs text-muted-foreground">
              Starter enables code lookup only. Pro enables clients, catalog, subscriptions, and reminders.
            </p>
          </div>
```

- [ ] **Step 3: Send plan from Master dashboard**

In `dashboard-page.tsx`, update `openEdit()` form state:

```ts
      plan: tenant.plan,
```

In `handleSubmit()`, validate:

```ts
    if (!form.plan) {
      setFormError("Plan is required.");
      return;
    }
```

In edit payload:

```ts
          plan: form.plan,
```

In create payload:

```ts
          plan: form.plan,
```

In `manageCatalog()`, after switch succeeds, navigate to admin dashboard. Import `useNavigate`:

```ts
import { useNavigate } from "@tanstack/react-router";
```

Inside component:

```ts
  const navigate = useNavigate();
```

After `toast.success(...)`:

```ts
      navigate({ to: "/admin/dashboard" });
```

- [ ] **Step 4: Show Plan badge in business table**

In `business-table.tsx`, add helper:

```tsx
function PlanBadge({ plan }: { plan: Tenant["plan"] }) {
  return <Badge variant={plan === "pro" ? "default" : "secondary"}>{plan === "pro" ? "Pro" : "Starter"}</Badge>;
}
```

Desktop table: add header after Business:

```tsx
<TableHead>Plan</TableHead>
```

Add cell after Business cell:

```tsx
<TableCell><PlanBadge plan={tenant.plan} /></TableCell>
```

Mobile card: show plan next to status:

```tsx
<div className="flex items-center gap-2">
  <PlanBadge plan={tenant.plan} />
  <StatusBadge active={tenant.is_active} />
</div>
```

- [ ] **Step 5: Build**

```bash
cd frontend && npm run build
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add frontend/src/features/master/services/tenant-api.ts frontend/src/features/master/components/business-form-dialog.tsx frontend/src/features/master/components/business-table.tsx frontend/src/features/master/components/dashboard-page.tsx
git commit -m "feat: manage tenant plan in master dashboard"
```

---

### Task 3: Plan-aware admin navigation and frontend 404 for Pro-only routes

**Files:**
- Create: `frontend/src/features/admin/components/not-found-page.tsx`
- Create: `frontend/src/features/admin/components/plan-route-gate.tsx`
- Create: `frontend/src/features/admin/components/support-banner.tsx`
- Modify: `frontend/src/features/admin/layout/admin-layout.tsx:1-113`
- Modify: `frontend/src/routes/admin/clients.tsx:1-7`
- Modify: `frontend/src/routes/admin/catalog.tsx:1-7`
- Modify: `frontend/src/routes/admin/subscriptions.tsx:1-7`

**Interfaces:**
- Consumes: `useAuthStore().tenantPlan` and `isMasterSupportContext`.
- Produces: tenant admin Starter does not see Clients/Catalog/Subscriptions links.
- Produces: tenant admin Starter direct route to Pro-only page renders frontend 404.
- Produces: Master switched into Starter sees full nav plus support banner.

- [ ] **Step 1: Create 404 component**

Create `frontend/src/features/admin/components/not-found-page.tsx`:

```tsx
import { Link } from "@tanstack/react-router";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

export function NotFoundPage() {
  return (
    <div className="flex min-h-[60vh] items-center justify-center p-6">
      <Card className="w-full max-w-md">
        <CardHeader>
          <CardTitle>404</CardTitle>
        </CardHeader>
        <CardContent className="flex flex-col gap-4">
          <p className="text-sm text-muted-foreground">This page is not available.</p>
          <Button asChild>
            <Link to="/admin/dashboard">Go to dashboard</Link>
          </Button>
        </CardContent>
      </Card>
    </div>
  );
}
```

- [ ] **Step 2: Create route gate**

Create `frontend/src/features/admin/components/plan-route-gate.tsx`:

```tsx
import type { ReactNode } from "react";
import { useAuthStore } from "@/store/auth";
import { NotFoundPage } from "./not-found-page";

export function PlanRouteGate({ children }: { children: ReactNode }) {
  const { role, tenantPlan, isMasterSupportContext } = useAuthStore();
  const isStarterTenantAdmin = role === "tenant" && tenantPlan === "starter";

  if (isStarterTenantAdmin && !isMasterSupportContext) {
    return <NotFoundPage />;
  }

  return <>{children}</>;
}
```

- [ ] **Step 3: Create support banner**

Create `frontend/src/features/admin/components/support-banner.tsx`:

```tsx
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";

export function SupportBanner() {
  return (
    <Alert className="m-4 mb-0">
      <AlertTitle className="flex items-center gap-2">
        Support mode <Badge variant="secondary">Starter tenant</Badge>
      </AlertTitle>
      <AlertDescription>
        You are viewing the full Pro admin surface as Master support. Starter tenant admins cannot see these Pro-only modules.
      </AlertDescription>
    </Alert>
  );
}
```

- [ ] **Step 4: Wrap Pro-only route files**

Update `frontend/src/routes/admin/clients.tsx`:

```tsx
import { createFileRoute } from "@tanstack/react-router";
import { ClientsPage } from "@/features/admin/components/clients-page";
import { PlanRouteGate } from "@/features/admin/components/plan-route-gate";

export const Route = createFileRoute("/admin/clients")({
  component: () => (
    <PlanRouteGate>
      <ClientsPage />
    </PlanRouteGate>
  ),
});
```

Apply the same wrapper to `catalog.tsx` and `subscriptions.tsx` with their page components.

- [ ] **Step 5: Filter admin navigation**

In `admin-layout.tsx`, import support banner:

```ts
import { SupportBanner } from "@/features/admin/components/support-banner";
```

Change auth store destructure:

```ts
  const { username, logout, role, tenantPlan, isMasterSupportContext } = useAuthStore();
```

Build nav with Pro-only marker:

```ts
  const isStarterTenantAdmin = role === "tenant" && tenantPlan === "starter";
  const showProNav = !isStarterTenantAdmin || isMasterSupportContext;
  const NAV_ITEMS = [
    { to: "/admin/dashboard", label: t("frontend.dashboard.tenant.title"), icon: LayoutDashboard, proOnly: false },
    { to: "/admin/clients", label: t("frontend.clients.section_title"), icon: Users, proOnly: true },
    { to: "/admin/catalog", label: t("frontend.catalog.section_title"), icon: Package, proOnly: true },
    { to: "/admin/subscriptions", label: t("frontend.subscriptions.title"), icon: CreditCard, proOnly: true },
    { to: "/admin/settings", label: t("frontend.settings.section_title"), icon: Settings, proOnly: false },
  ].filter((item) => showProNav || !item.proOnly);
```

In `<main>`, render support banner before outlet:

```tsx
      <main className="flex-1 overflow-y-auto md:pt-0 pt-14">
        {isMasterSupportContext && tenantPlan === "starter" && <SupportBanner />}
        <Outlet />
      </main>
```

- [ ] **Step 6: Build**

```bash
cd frontend && npm run build
```

Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add frontend/src/features/admin/components/not-found-page.tsx frontend/src/features/admin/components/plan-route-gate.tsx frontend/src/features/admin/components/support-banner.tsx frontend/src/features/admin/layout/admin-layout.tsx frontend/src/routes/admin/clients.tsx frontend/src/routes/admin/catalog.tsx frontend/src/routes/admin/subscriptions.tsx
git commit -m "feat: gate pro admin routes by tenant plan"
```

---

### Task 4: Plan-aware Settings and product labels

**Files:**
- Modify: `frontend/src/features/admin/components/settings-page.tsx:1-133`
- Modify: `frontend/src/features/admin/components/mailbox-section.tsx:1-348`
- Modify: `frontend/src/features/admin/components/code-services-section.tsx:1-124`
- Modify: `frontend/src/features/admin/services/settings-api.ts:91-103`
- Backend i18n keys are added in backend plan Task 7.

**Interfaces:**
- Consumes: `tenantPlan`, `isMasterSupportContext`.
- Produces Starter Settings: Profile, Locale, Correo central de búsqueda, Plataformas habilitadas, Control de acceso, Password.
- Produces Pro Settings: Profile, Locale, Timezone, Correo central de búsqueda, Plataformas habilitadas, Reminder settings, Control de acceso, Password.
- Produces Master-switched Starter Settings: full settings.

- [ ] **Step 1: Allow nullable timezone type**

In `settings-api.ts`, change:

```ts
  timezone: string;
```

To:

```ts
  timezone: string | null;
```

- [ ] **Step 2: Import auth state**

In `settings-page.tsx`, add import:

```ts
import { useAuthStore } from "@/store/auth";
```

- [ ] **Step 3: Build filtered sections**

Replace the `SECTIONS` constant with a plan-aware list inside component:

```tsx
  const { role, tenantPlan, isMasterSupportContext } = useAuthStore();
  const isStarterTenantAdmin = role === "tenant" && tenantPlan === "starter";
  const showProSettings = !isStarterTenantAdmin || isMasterSupportContext;

  const SECTIONS = [
    ...(showProSettings ? [{ id: "reminders", title: t("frontend.subscriptions.reminder_settings_title"), description: t("frontend.subscriptions.reminders_desc"), icon: Bell }] : []),
    { id: "locale", title: t("frontend.profile.language"), description: t("frontend.profile.language"), icon: Globe },
    ...(showProSettings ? [{ id: "timezone", title: t("frontend.subscriptions.timezone"), description: "Set your tenant timezone for subscriptions and reminders", icon: Clock }] : []),
    { id: "code-services", title: t("frontend.code_services.tenant_section_title"), description: t("frontend.code_services.tenant_description"), icon: Shield },
    { id: "mailbox", title: t("frontend.mailbox.section_title"), description: t("frontend.mailbox.section_heading"), icon: Mail },
    { id: "profile", title: t("frontend.profile.section_title"), description: t("frontend.profile.section_heading"), icon: User },
    { id: "password", title: t("frontend.dashboard.client.change_password"), description: t("frontend.dashboard.client.change_password"), icon: Lock },
  ] as const;
```

- [ ] **Step 4: Confirm Pro-only settings are filtered**

Verify the `reminders` and `timezone` entries are only present when `showProSettings` is true. Starter tenant admins should still see Locale, Plataformas habilitadas, Correo central de búsqueda, Profile, and Password after this task; Control de acceso is added in Task 5 so the component exists before it is imported.

- [ ] **Step 5: Add help icon with native tooltip for mailbox**

In `mailbox-section.tsx`, import `HelpCircle`:

```ts
import { Mail, CheckCircle2, AlertCircle, Unplug, HelpCircle } from "lucide-react";
```

At the top of returned content, before current status:

```tsx
      <div className="flex items-start justify-between gap-3">
        <div className="flex flex-col gap-1">
          <h2 className="text-base font-medium">{t("frontend.mailbox.section_title")}</h2>
          <p className="text-sm text-muted-foreground">{t("frontend.mailbox.product_description")}</p>
        </div>
        <HelpCircle className="size-4 text-muted-foreground" title={t("frontend.mailbox.product_tooltip")} />
      </div>
```

- [ ] **Step 6: Add help icon with native tooltip for code services**

In `code-services-section.tsx`, import `HelpCircle`:

```ts
import { HelpCircle } from "lucide-react";
```

Replace the first paragraph with:

```tsx
      <div className="flex items-start justify-between gap-3">
        <div className="flex flex-col gap-1">
          <h2 className="text-base font-medium">{t("frontend.code_services.tenant_section_title")}</h2>
          <p className="text-sm text-muted-foreground">{t("frontend.code_services.product_description")}</p>
        </div>
        <HelpCircle className="size-4 text-muted-foreground" title={t("frontend.code_services.product_tooltip")} />
      </div>
```

- [ ] **Step 7: Add frontend i18n keys in backend catalogs**

In `backend/app/core/i18n/catalogs_es_frontend.py`, update visible labels:

```python
"frontend.mailbox.section_title": "Correo central de búsqueda",
"frontend.mailbox.section_heading": "Configura el correo central que recibe los mensajes de las plataformas habilitadas.",
"frontend.mailbox.product_tooltip": "Conecta el correo donde TrackPal buscará códigos de acceso.",
"frontend.mailbox.product_description": "Configura el correo central que recibe los mensajes de las plataformas habilitadas. TrackPal lo usa para buscar códigos de acceso por email cuando un usuario inicia el flujo de búsqueda de códigos.",
"frontend.code_services.tenant_section_title": "Plataformas habilitadas",
"frontend.code_services.tenant_section_heading": "Plataformas habilitadas",
"frontend.code_services.product_tooltip": "Define qué plataformas estarán disponibles para buscar códigos de acceso por email.",
"frontend.code_services.product_description": "Selecciona las plataformas donde TrackPal puede buscar códigos de acceso por email, como Netflix, Disney+ o Spotify. Solo las plataformas habilitadas estarán disponibles en el flujo de búsqueda de códigos.",
"frontend.access_control.section_title": "Control de acceso",
"frontend.access_control.section_description": "Bloquea o desbloquea identidades de WhatsApp para el bot y la búsqueda de códigos.",
"frontend.access_control.phone_placeholder": "+584241234567",
"frontend.access_control.block": "Bloquear teléfono",
"frontend.access_control.unblock": "Desbloquear",
"frontend.access_control.empty": "No hay identidades bloqueadas.",
"frontend.access_control.saved": "Control de acceso actualizado.",
```

Add English equivalents to `catalogs_en_frontend.py`.

- [ ] **Step 8: Build**

```bash
cd frontend && npm run build
```

Expected: PASS.

- [ ] **Step 9: Commit**

```bash
git add frontend/src/features/admin/components/settings-page.tsx frontend/src/features/admin/components/mailbox-section.tsx frontend/src/features/admin/components/code-services-section.tsx frontend/src/features/admin/services/settings-api.ts backend/app/core/i18n/catalogs_en_frontend.py backend/app/core/i18n/catalogs_es_frontend.py
git commit -m "feat: show plan-aware settings labels"
```

---

### Task 5: Control de acceso Settings UI

**Files:**
- Create: `frontend/src/features/admin/services/access-control-api.ts`
- Create: `frontend/src/features/admin/components/access-control-section.tsx`
- Modify: `frontend/src/features/admin/components/settings-page.tsx:1-133`

**Interfaces:**
- Consumes: backend `/access-control/blocks` from backend plan Task 6.
- Produces: list active blocks, block phone, unblock.

- [ ] **Step 1: Create API service**

Create `frontend/src/features/admin/services/access-control-api.ts`:

```ts
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
```

- [ ] **Step 2: Create section component**

Create `frontend/src/features/admin/components/access-control-section.tsx`:

```tsx
import { useCallback, useEffect, useState } from "react";
import { toast } from "sonner";
import { Ban, Trash2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Badge } from "@/components/ui/badge";
import { t } from "@/i18n";
import {
  createAccessBlock,
  deleteAccessBlock,
  listAccessBlocks,
  type AccessControlBlock,
} from "../services/access-control-api";

function getApiError(error: unknown, fallback: string): string {
  const err = error as { response?: { data?: { detail?: string | Array<{ msg?: string }> } } };
  const detail = err.response?.data?.detail;
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail)) return detail.map((item) => item.msg || String(item)).join(", ");
  return error instanceof Error ? error.message : fallback;
}

export function AccessControlSection() {
  const [blocks, setBlocks] = useState<AccessControlBlock[]>([]);
  const [phone, setPhone] = useState("");
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      setBlocks(await listAccessBlocks());
    } catch (error) {
      toast.error(getApiError(error, t("frontend.access_control.error_load")));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  async function handleBlock(e: React.FormEvent) {
    e.preventDefault();
    if (!phone.trim()) return;
    setSaving(true);
    try {
      await createAccessBlock(phone);
      setPhone("");
      await load();
      toast.success(t("frontend.access_control.saved"));
    } catch (error) {
      toast.error(getApiError(error, t("frontend.access_control.error_save")));
    } finally {
      setSaving(false);
    }
  }

  async function handleUnblock(id: string) {
    setSaving(true);
    try {
      await deleteAccessBlock(id);
      await load();
      toast.success(t("frontend.access_control.saved"));
    } catch (error) {
      toast.error(getApiError(error, t("frontend.access_control.error_save")));
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="flex flex-col gap-4">
      <form onSubmit={handleBlock} className="flex flex-col gap-3 sm:flex-row sm:items-end">
        <div className="flex flex-1 flex-col gap-2">
          <Label htmlFor="access-control-phone">{t("frontend.access_control.block")}</Label>
          <Input
            id="access-control-phone"
            value={phone}
            onChange={(event) => setPhone(event.target.value)}
            placeholder={t("frontend.access_control.phone_placeholder")}
          />
        </div>
        <Button type="submit" disabled={saving || !phone.trim()}>
          <Ban data-icon="inline-start" />
          {t("frontend.access_control.block")}
        </Button>
      </form>

      {loading ? (
        <div className="h-16 rounded-lg bg-muted" />
      ) : blocks.length === 0 ? (
        <p className="text-sm text-muted-foreground">{t("frontend.access_control.empty")}</p>
      ) : (
        <div className="flex flex-col gap-2">
          {blocks.map((block) => (
            <div key={block.id} className="flex items-center justify-between rounded-lg border p-3">
              <div className="flex items-center gap-2">
                <Badge variant="secondary">{block.phone || block.whatsapp_lid || "—"}</Badge>
              </div>
              <Button variant="ghost" size="sm" disabled={saving} onClick={() => handleUnblock(block.id)}>
                <Trash2 data-icon="inline-start" />
                {t("frontend.access_control.unblock")}
              </Button>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
```

- [ ] **Step 3: Add Access Control to SettingsPage**

In `settings-page.tsx`, import the component:

```ts
import { AccessControlSection } from "./access-control-section";
```

Add the section entry after mailbox:

```tsx
    { id: "access-control", title: t("frontend.access_control.section_title"), description: t("frontend.access_control.section_description"), icon: Shield },
```

Add the expanded renderer after mailbox/code-services render blocks:

```tsx
                  {section.id === "access-control" && isOpen && (
                    <div className="mt-4">
                      <AccessControlSection />
                    </div>
                  )}
```

- [ ] **Step 4: Ensure missing i18n keys exist**

Add English keys in `backend/app/core/i18n/catalogs_en_frontend.py`:

```python
"frontend.access_control.error_load": "Unable to load access control blocks.",
"frontend.access_control.error_save": "Unable to update access control.",
```

Add Spanish keys in `backend/app/core/i18n/catalogs_es_frontend.py`:

```python
"frontend.access_control.error_load": "No se pudo cargar el control de acceso.",
"frontend.access_control.error_save": "No se pudo actualizar el control de acceso.",
```

- [ ] **Step 5: Build**

```bash
cd frontend && npm run build
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add frontend/src/features/admin/services/access-control-api.ts frontend/src/features/admin/components/access-control-section.tsx frontend/src/features/admin/components/settings-page.tsx backend/app/core/i18n/catalogs_en_frontend.py backend/app/core/i18n/catalogs_es_frontend.py
git commit -m "feat: add access control settings UI"
```

---

### Task 6: Tenant dashboard widgets and stale plan correction

**Files:**
- Create: `frontend/src/features/admin/services/dashboard-api.ts`
- Modify: `frontend/src/features/admin/components/dashboard-page.tsx:1-47`
- Modify: `frontend/src/store/auth.ts:13-125` if `setTenantPlan` was not added in Task 1.

**Interfaces:**
- Consumes: backend `GET /dashboard` tenant payload from backend plan Task 5.
- Produces: dashboard corrects `authStore.tenantPlan` when response differs.
- Produces: Starter common widgets and Pro-only metric widgets.

- [ ] **Step 1: Create dashboard API service**

Create `frontend/src/features/admin/services/dashboard-api.ts`:

```ts
import api from "@/lib/api";
import type { TenantPlan } from "@/features/auth/services/auth-api";

export interface TenantDashboardResponse {
  message: string;
  full_name: string;
  email: string | null;
  tenant_plan: TenantPlan;
  mailbox_status: string;
  enabled_code_services: string[];
  access_control_count: number;
  active_clients: number | null;
  catalog_services: number | null;
  active_subscriptions: number | null;
  subscriptions_expiring_soon: number | null;
}

export async function getTenantDashboard(): Promise<TenantDashboardResponse> {
  const { data } = await api.get("/dashboard");
  return data;
}
```

- [ ] **Step 2: Replace placeholder dashboard**

Replace `frontend/src/features/admin/components/dashboard-page.tsx` with:

```tsx
import { useCallback, useEffect, useState } from "react";
import { Navigate } from "@tanstack/react-router";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { useAuthStore } from "@/store/auth";
import { t } from "@/i18n";
import { getTenantDashboard, type TenantDashboardResponse } from "../services/dashboard-api";
import { Ban, CheckCircle2, Database, LogOut, Mail, Package, Users } from "lucide-react";

function MetricCard({ title, value, icon: Icon }: { title: string; value: string | number; icon: typeof Users }) {
  return (
    <Card>
      <CardHeader className="flex flex-row items-center justify-between pb-2">
        <CardTitle className="text-sm font-medium">{title}</CardTitle>
        <Icon className="size-4 text-muted-foreground" />
      </CardHeader>
      <CardContent>
        <div className="text-2xl font-bold">{value}</div>
      </CardContent>
    </Card>
  );
}

export function DashboardPage() {
  const { isAuthenticated, role, username, logout, tenantPlan, setTenantPlan } = useAuthStore();
  const [dashboard, setDashboard] = useState<TenantDashboardResponse | null>(null);
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const data = await getTenantDashboard();
      setDashboard(data);
      if (data.tenant_plan !== tenantPlan) {
        setTenantPlan(data.tenant_plan);
      }
    } finally {
      setLoading(false);
    }
  }, [setTenantPlan, tenantPlan]);

  useEffect(() => {
    if (isAuthenticated) load();
  }, [isAuthenticated, load]);

  if (!isAuthenticated || (role !== "tenant" && role !== "master")) {
    return <Navigate to="/login" replace />;
  }

  if (loading || !dashboard) {
    return <div className="p-6 text-sm text-muted-foreground">Loading...</div>;
  }

  const isPro = dashboard.tenant_plan === "pro";

  return (
    <div className="flex-1 p-6">
      <div className="mx-auto flex max-w-6xl flex-col gap-6">
        <div className="flex items-center justify-between gap-4">
          <div className="flex flex-col gap-1">
            <div className="flex items-center gap-2">
              <h1 className="text-2xl font-bold tracking-tight">{t("frontend.dashboard.tenant.title")}</h1>
              <Badge variant={isPro ? "default" : "secondary"}>{isPro ? "Pro" : "Starter"}</Badge>
            </div>
            <p className="text-muted-foreground">{t("frontend.dashboard.tenant.welcome", { name: username || "Admin" })}</p>
          </div>
          <Button variant="outline" size="sm" onClick={() => logout()}>
            <LogOut data-icon="inline-start" />
            {t("frontend.dashboard.tenant.logout")}
          </Button>
        </div>

        <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
          <MetricCard title="Plan" value={isPro ? "Pro" : "Starter"} icon={CheckCircle2} />
          <MetricCard title={t("frontend.mailbox.section_title")} value={dashboard.mailbox_status} icon={Mail} />
          <MetricCard title={t("frontend.code_services.tenant_section_title")} value={dashboard.enabled_code_services.length} icon={Package} />
          <MetricCard title={t("frontend.access_control.section_title")} value={dashboard.access_control_count} icon={Ban} />
        </div>

        {dashboard.enabled_code_services.length > 0 && (
          <Card>
            <CardHeader><CardTitle>{t("frontend.code_services.tenant_section_title")}</CardTitle></CardHeader>
            <CardContent className="flex flex-wrap gap-2">
              {dashboard.enabled_code_services.map((service) => <Badge key={service} variant="secondary">{service}</Badge>)}
            </CardContent>
          </Card>
        )}

        {isPro && (
          <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
            <MetricCard title={t("frontend.clients.section_title")} value={dashboard.active_clients ?? 0} icon={Users} />
            <MetricCard title={t("frontend.catalog.section_title")} value={dashboard.catalog_services ?? 0} icon={Database} />
            <MetricCard title={t("frontend.subscriptions.title")} value={dashboard.active_subscriptions ?? 0} icon={CheckCircle2} />
            <MetricCard title={t("frontend.dashboard.expiring_soon")} value={dashboard.subscriptions_expiring_soon ?? 0} icon={Mail} />
          </div>
        )}
      </div>
    </div>
  );
}
```

- [ ] **Step 3: Add dashboard i18n key**

English catalog:

```python
"frontend.dashboard.expiring_soon": "Expiring in 7 days",
```

Spanish catalog:

```python
"frontend.dashboard.expiring_soon": "Vencen en 7 días",
```

- [ ] **Step 4: Build**

```bash
cd frontend && npm run build
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/features/admin/services/dashboard-api.ts frontend/src/features/admin/components/dashboard-page.tsx backend/app/core/i18n/catalogs_en_frontend.py backend/app/core/i18n/catalogs_es_frontend.py
git commit -m "feat: show plan-aware tenant dashboard"
```

---

### Task 7: Frontend docs and final verification

**Files:**
- Modify: `docs/architecture/frontend-architecture.md`
- Modify: `docs/codebase/frontend-components.md`
- Modify: `docs/codebase/frontend-structure.md`
- Modify: `docs/code-standard/frontend-conventions.md`

**Interfaces:**
- Consumes: all frontend changes.
- Produces: docs that describe `tenantPlan`, plan-aware admin routes, support banner, Control de acceso Settings section, and product labels.

- [ ] **Step 1: Update frontend architecture docs**

In `docs/architecture/frontend-architecture.md`, add under Auth Store:

```markdown
- `tenantPlan`: `starter | pro | null`, persisted from auth responses and corrected by tenant dashboard responses. This is only a UI hint; backend gates remain authoritative.
- `isMasterSupportContext`: true when Master is switched into a tenant (`role=master` + `activeTenantId`). Master support sees the full admin surface and a support banner.
```

Under Routing, add:

```markdown
Starter tenant admins see 404 for direct navigation to Pro-only admin routes (`/admin/clients`, `/admin/catalog`, `/admin/subscriptions`). Master support context bypasses this frontend gate to inspect preserved Pro data.
```

- [ ] **Step 2: Update component docs**

In `docs/codebase/frontend-components.md`, update SettingsPage section with:

```markdown
Starter Settings shows Profile, Language, Correo central de búsqueda, Plataformas habilitadas, Control de acceso, and Password. Pro adds Timezone and Reminder Settings. Master support context shows the full Pro settings set even for Starter tenants.
```

Add `AccessControlSection` to Admin Feature Components:

```markdown
### AccessControlSection (`features/admin/components/access-control-section.tsx`)

Lists active WhatsApp access blocks, blocks a phone, and unblocks existing entries through `/access-control/blocks`. This affects bot/code interactions only, not client portal accounts.
```

- [ ] **Step 3: Update frontend structure docs**

In `docs/codebase/frontend-structure.md`, add created files under `features/admin/components` and `features/admin/services`.

- [ ] **Step 4: Update conventions**

In `docs/code-standard/frontend-conventions.md`, add:

```markdown
Plan-aware UI gates are convenience only. Do not use frontend `tenantPlan` as authorization. Pro-only backend calls must still expect 404 for Starter tenants.
```

- [ ] **Step 5: Run frontend verification**

```bash
cd frontend && npm run build
cd frontend && npm run lint
```

Expected: both PASS.

- [ ] **Step 6: Run cross-context smoke tests**

```bash
cd backend && uv run pytest tests/test_tenant_plan.py tests/test_access_control_api.py -q
```

Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add docs/architecture/frontend-architecture.md docs/codebase/frontend-components.md docs/codebase/frontend-structure.md docs/code-standard/frontend-conventions.md
git commit -m "docs: document starter pro frontend split"
```
