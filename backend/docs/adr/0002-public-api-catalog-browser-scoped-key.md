# Public API Catalog uses readable keys with browser-origin scope

The Public API Catalog is read-only and intended for tenant-owned browser frontends, so v1 stores one visible Public API Key per Pro tenant and requires every public catalog request to include an exact registered `Origin`. This deliberately avoids hashed one-time-display keys and app-level rate limiting for now: tenants need to recover the key from Settings, non-browser/server-to-server use is out of scope, and production abuse protection belongs at Cloudflare because the backend runs on Render free tier.

**Considered options:**
- *Hashed key with one-time display*: stronger for future write/sensitive scopes, but creates avoidable tenant support friction for a read-only catalog.
- *App-level rate limiting with slowapi/Redis*: easier to see in code, but in-memory resets on Render cold starts and Redis rate limiting would spend limited free-tier capacity.
- *Wildcard domains or requests without Origin*: more flexible, but weakens the browser-only integration boundary for v1.

**Consequences:**
- If the public API later exposes sensitive data or mutations, key storage should move to hashed-at-rest with one-time display.
- Cloudflare rate limiting/WAF for the public catalog route is an operational requirement, not optional app behavior.
- Allowed origins are exact scheme/host/port values; wildcard origins and server-to-server usage need a separate decision.
