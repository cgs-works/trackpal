# Public API Catalog

Public API Catalog is an implemented Pro-only feature tracked by GitHub Issue #73. It lets tenants publish their TrackPal catalog to tenant-owned browser frontends without duplicating service and plan names outside TrackPal.

## Product Rules

1. Only Pro tenants can configure and use Public API Catalog.
2. Starter tenants do not see Public API Key management in Settings.
3. If a Pro tenant downgrades to Starter, public catalog access returns 403 but the key configuration is preserved.
4. Each tenant has at most one active Public API Key in v1.
5. The key is visible in Settings, revocable, and regenerable.
6. Regenerating the key replaces the key while preserving Allowed Origins.
7. Revoking the key removes the public API configuration and disables access.
8. Allowed Origins are exact browser origins including scheme, host, and optional port.
9. Wildcard origins are out of scope for v1.
10. Public catalog requests require both a valid Public API Key and a matching `Origin` header.
11. Requests without `Origin` are out of scope for v1 and return 403.
12. The public payload returns services with nested plans, each limited to `id` and `name`.
13. Pricing, availability, descriptions, and metadata are out of scope for v1.
14. Server-to-server usage is out of scope for v1 because non-browser clients can spoof `Origin`.
15. Production must protect the public catalog route with Cloudflare rate limiting/WAF; app-level rate limiting is explicitly deferred.
16. Demo Tenants cannot configure or call the real Public API Catalog. Starter demos retain the normal plan gate; Pro demos show a disabled capability preview backed only by the browser-local workspace. Direct Demo JWT or demo-key attempts are rejected by the Demo Guardrail.

## UX Rules

- Public API Key management lives in the tenant Settings page as a Pro-only section.
- Master Support Context may see the section to troubleshoot tenant integrations.
- UI copy should use the backend-sourced frontend i18n catalog.
- Settings provides a localized developer handoff package with maintained HTML + JavaScript, React, Vue, Svelte, Angular, and Alpine.js examples.
- The handoff package uses `YOUR_PUBLIC_API_KEY` as a placeholder and must never include the Tenant's real key automatically; the real key is shared separately through a secure channel.
- Pro Demo Accounts keep the section discoverable but disable key/origin creation, regeneration, copy, revoke, and external catalog access with demo-specific explanation.


## Related Decision

See `backend/docs/adr/0002-public-api-catalog-browser-scoped-key.md` for the key visibility, Origin scope, and Cloudflare rate-limiting decision.

## Browser Request Example

```js
const response = await fetch(
  "https://api.trackpal.example/api/v1/public/catalog?api_key=tpk_example"
);
const catalog = await response.json();
```

A browser automatically sends `Origin`. The backend only returns `Access-Control-Allow-Origin` when that origin exactly matches one registered Allowed Origin for the key.

Example response:

```json
{
  "services": [
    {
      "id": "00000000-0000-0000-0000-000000000001",
      "name": "Netflix",
      "plans": [
        {
          "id": "00000000-0000-0000-0000-000000000002",
          "name": "Premium"
        }
      ]
    }
  ]
}

## Required Cloudflare Protection

Before broad exposure, production must add a Cloudflare WAF/rate-limit rule for:

- Method: `GET`
- Path: `/api/v1/public/catalog`
- Action: rate-limit or managed challenge after abusive request volume
- Scope: all public traffic

Do not add FastAPI, Redis, or in-memory rate limiting for v1.
