# Data Flow

## Authentication flow

```
Client                     FastAPI                     Supabase
  │                          │                          │
  │ POST /auth/login         │                          │
  │ {username, password}     │                          │
  ├─────────────────────────>│                          │
  │                          │ SELECT user WHERE username│
  │                          ├─────────────────────────>│
  │                          │<─────────────────────────┤
  │                          │ verify_password(bcrypt)  │
  │                          │ SELECT tenant_profile    │
  │                          │  (check is_active)       │
  │                          │ INSERT refresh_session   │
  │                          ├─────────────────────────>│
  │ 200 {access_token,       │                          │
  │      refresh_token,      │                          │
  │      user}               │                          │
  │<─────────────────────────┤                          │
```

## Token refresh flow

```
Client                     FastAPI                     Supabase
  │                          │                          │
  │ POST /auth/refresh       │                          │
  │ {refresh_token}          │                          │
  ├─────────────────────────>│                          │
  │                          │ decode JWT (type=refresh)│
  │                          │ SELECT refresh_sessions  │
  │                          │  (user_id, not revoked)  │
  │                          ├─────────────────────────>│
  │                          │<─────────────────────────┤
  │                          │ verify hash match        │
  │                          │ revoke old session       │
  │                          │ check tenant is_active   │
  │                          │ INSERT new session       │
  │                          ├─────────────────────────>│
  │ 200 {new access_token,   │                          │
  │      new refresh_token}  │                          │
  │<─────────────────────────┤                          │
```

## n8n → Evolution API → WhatsApp flow (legacy)

> **Legacy (pre-May 2026):** This is the original implementation where n8n managed session state and called CRUD endpoints directly. **Current architecture** (WhatsApp Credential Auth, 2026-05-13) uses n8n as **transport-only**:
>
> `WhatsApp → Evolution API → n8n (parse) → POST /api/v1/integrations/n8n/console → Backend (Redis auth + session + logic) → reply → n8n → Evolution API → WhatsApp`
>
> The backend gates console behind Redis auth session (`wa:auth:{phone}`) created after conversational username+password login. See the [WhatsApp Master Console (credential auth)](#whatsapp-master-console-credential-auth) section below for the current flow, ADR-0004 for session architecture, and ADR-0003 for transport-only n8n.

```
WhatsApp User            Evolution API          n8n Workflow            Trackpal API
     │                       │                     │                       │
     │ sends message         │                     │                       │
     ├──────────────────────>│                     │                       │
     │                       │ POST /webhook/      │                       │
     │                       │ trackpal-whatsapp-  │                       │
     │                       │ bot (payload)       │                       │
     │                       ├────────────────────>│                       │
     │                       │                     │ Parse input           │
     │                       │                     │ (extract phone, msg)  │
     │                       │                     │                       │
     │                       │                     │ GET /identify?phone=  │
     │                       │                     │ (X-API-Key)           │
     │                       │                     ├──────────────────────>│
     │                       │                     │<──────────────────────┤
     │                       │                     │                       │
     │                       │                     │ Session lookup        │
     │                       │                     │ (Data Table Get)      │
     │                       │                     │                       │
     │                       │                     │ Step handler / Menu   │
     │                       │                     │ (Code node)           │
     │                       │                     │                       │
     │                       │                     │ CRUD via API:         │
     │                       │                     │ POST/GET/PATCH/DELETE │
     │                       │                     │ /tenants/*            │
     │                       │                     ├──────────────────────>│
     │                       │                     │<──────────────────────┤
     │                       │                     │                       │
     │                       │                     │ Session update/delete │
     │                       │                     │ (Data Table Upsert/Del)│
     │                       │                     │                       │
     │                       │                     │ POST /message/sendText│
     │                       │<────────────────────┤                       │
     │<──────────────────────┤                     │                       │
     │ receives reply        │                     │                       │
```

## WhatsApp Master Console (credential auth)

> **Implemented in:** WhatsApp Credential Auth phase (2026-05-13).
> See ADR-0004 for session architecture and ADR-0003 for transport-only n8n.

The WhatsApp Master Console now requires conversational **username + password**
login. The flow is:

```
WhatsApp User            Evolution API          n8n (transport only)      Trackpal Backend    Redis
     │                       │                     │                       │                    │
     │ sends message         │                     │                       │                    │
     ├──────────────────────>│                     │                       │                    │
     │                       │ POST /webhook/      │                       │                    │
     │                       │ /trackpal-whatsapp- │                       │                    │
     │                       │ bot (payload)       │                       │                    │
     │                       ├────────────────────>│                       │                    │
     │                       │                     │ Parse input           │                    │
     │                       │                     │ (phone, message,      │                    │
     │                       │                     │  instance)            │                    │
     │                       │                     │                       │                    │
     │                       │                     │ POST /n8n/console     │                    │
     │                       │                     │ {phone, message,      │                    │
     │                       │                     │  instance}            │                    │
     │                       │                     ├──────────────────────>│                    │
     │                       │                     │                       │ Check lockout      │
     │                       │                     │                       ├───────────────────>│
     │                       │                     │                       │<───────────────────┤
     │                       │                     │                       │                    │
     │                       │                     │                       │ Check auth session │
     │                       │                     │                       │ (wa:auth:{phone})  │
     │                       │                     │                       ├───────────────────>│
     │                       │                     │                       │<───────────────────┤
     │                       │                     │                       │                    │
     │                       │                     │  ── if no auth session ──                │
     │                       │                     │                       │                    │
     │                       │                     │                       │ Create flow session│
     │                       │                     │                       │ (session:{phone})  │
     │                       │                     │                       ├───────────────────>│
     │                       │                     │                       │<───────────────────┤
     │                       │                     │                       │                    │
     │                       │                     │  "¿Cuál es tu nombre  │                    │
     │                       │                     │   de usuario?"        │                    │
     │                       │                     │<──────────────────────┤                    │
     │                       │<────────────────────┤                       │                    │
     │<──────────────────────┤                     │                       │                    │
     │                       │                     │                       │                    │
     │  user replies username│                     │                       │                    │
     ├──────────────────────>│                     │                       │                    │
     │                       ├────────────────────>│                       │                    │
     │                       │                     ├──────────────────────>│                    │
     │                       │                     │                       │ Store username     │
     │                       │                     │                       ├───────────────────>│
     │                       │                     │                       │<───────────────────┤
     │                       │                     │  "Introduce tu        │                    │
     │                       │                     │   contraseña"         │                    │
     │                       │                     │<──────────────────────┤                    │
     │                       │<────────────────────┤                       │                    │
     │<──────────────────────┤                     │                       │                    │
     │                       │                     │                       │                    │
     │  user replies password│                     │                       │                    │
     ├──────────────────────>│                     │                       │                    │
     │                       ├────────────────────>│                       │                    │
     │                       │                     ├──────────────────────>│                    │
     │                       │                     │                       │                    │
     │                       │                     │                       │ AuthService.       │
     │                       │                     │                       │ authenticate(db,   │
     │                       │                     │                       │   username, pass)  │
     │                       │                     │                       │ ── Supabase ──>   │
     │                       │                     │                       │                    │
     │                       │                     │                       │  ── on success ──  │
     │                       │                     │                       │                    │
     │                       │                     │                       │ Create auth session│
     │                       │                     │                       │ (wa:auth:{phone})  │
     │                       │                     │                       │  TTL=15min         │
     │                       │                     │                       ├───────────────────>│
     │                       │                     │                       │<───────────────────┤
     │                       │                     │                       │                    │
     │                       │                     │                       │ Clear flow session │
     │                       │                     │                       ├───────────────────>│
     │                       │                     │                       │                    │
     │                       │                     │  "[Menú principal]"   │                    │
     │                       │                     │<──────────────────────┤                    │
     │                       │<────────────────────┤                       │                    │
     │<──────────────────────┤                     │                       │                    │
     │ receives menu        │                     │                       │                    │
```

### Gate: no bypass to menu/CRUD without auth

Every message hits `WhatsAppMasterConsoleFacade.process_message()` which:

1. Checks lockout (`wa:auth:lock:{phone}`) → returns lockout reply if locked.
2. Checks auth session (`wa:auth:{phone}`) → delegates to
   `WhatsAppConsoleService.process_message(is_master=True, ...)` if valid.
3. Otherwise runs conversational login flow (username → password → verify →
   create auth session).

Even if a user sends `1`, `2`, `menu`, or any CRUD-triggering option
**without** an active auth session, they are redirected to the username prompt.

### Auth session vs conversation session

- **Auth session** (`wa:auth:{phone}`, TTL 15 min sliding) — proof of
  authenticated identity. Persists across menu navigation and CRUD flows.
- **Conversation session** (`session:{phone}`, TTL 15 min sliding) —
  conversational flow state (step, temp data, selection map). Cleared on
  reset commands, flow completion, or cancellation.

The two are independent. Expiry or absence of either blocks console
access appropriately.

### Reset command behaviour per context

| Context | Command | Auth session | Conversation session |
|---|---|---|---|
| Authenticated, top-level | ``0`` | **Cleared** (full logout) | **Cleared** |
| Authenticated, top-level | ``menu``\/``cancelar`` | **Persists** | **Cleared** (return to menu) |
| Authenticated, sub-flow | ``0`` | **Refreshed** (``touch_auth_session``) | **Cleared** by console service |
| Authenticated, sub-flow | ``menu``\/``cancelar`` | **Persists** | **Cleared** (return to menu) |
| Unauthenticated (login) | ``0``\/``menu``\/``cancelar`` | **Cleared** (safety reset) | **Cleared** |

### Security trade-off (accepted)

- **Password over WhatsApp:** The password is transmitted through
  WhatsApp's E2E-encrypted channel (Evolution API relay). This is an
  accepted trade-off for operational flexibility: the Master Console
  can be used from any WhatsApp-registered device without VPN or
  dashboard access.
- **Mitigations:** Temporary lockout after 5 consecutive failures
  (5-minute lock window, 15-minute failure counter window). Auth session
  TTL of 15 minutes (sliding). No password stored in Redis payloads.
  Role verification restricts to `master` role only.
- **Future hardening:** Consider OTP, magic link, or QR-based
  device-trust for higher-security environments (explicitly out of
  scope for this iteration — see PRD).

## Logout flow (WhatsApp Master Console)

When the authenticated Master user sends ``0`` at the top-level menu, the
backend performs a full logout:

```
WhatsApp User            Backend (Facade)          Redis                 Evolution API
     │                         │                    │                        │
     │ sends "0"               │                    │                        │
     ├────────────────────────>│                    │                        │
     │                         │ Check auth session │                        │
     │                         │ (wa:auth:{phone})  │                        │
     │                         ├───────────────────>│                        │
     │                         │<───────────────────┤                        │
     │                         │                    │                        │
     │                         │ Check conv session │                        │
     │                         │ (session:{phone})  │                        │
     │                         ├───────────────────>│                        │
     │                         │<───────────────────┤                        │
     │                         │ no active flow     │                        │
     │                         │                    │                        │
     │                         │ Clear auth session │                        │
     │                         │ (DEL wa:auth:..)   │                        │
     │                         ├───────────────────>│                        │
     │                         │<───────────────────┤                        │
     │                         │                    │                        │
     │                         │ Clear conv session │                        │
     │                         │ (DEL session:..)   │                        │
     │                         ├───────────────────>│                        │
     │                         │<───────────────────┤                        │
     │                         │                    │                        │
     │                         │ POST /n8n/         │                        │
     │                         │ changeStatus/      │                        │
     │                         │ {instance}         │                        │
     │                         │ {remoteJid,        │                        │
     │                         │  status:"closed"}   │                        │
     │                         ├───────────────────────────────────────────────>│
     │                         │<───────────────────────────────────────────────┤
     │                         │                    │                        │
     │ "Sesión cerrada"       │                    │                        │
     │<────────────────────────┤                    │                        │
```

If the Evolution API call fails (e.g. instance not found), the error is
logged as a warning and the logout still completes — the user is logged out
locally regardless of the Evolution API outcome.

## Tenant deactivation flow

```
Master                     FastAPI                  Supabase
  │                          │                       │
  │ POST /tenants/{id}/      │                       │
  │ deactivate               │                       │
  ├─────────────────────────>│                       │
  │                          │ UPDATE tenant_profile │
  │                          │  SET is_active=false  │
  │                          ├──────────────────────>│
  │                          │                       │
  │                          │ UPDATE refresh_session│
  │                          │  SET revoked=true     │
  │                          │  WHERE user_id={id}   │
  │                          ├──────────────────────>│
  │ 200 {deactivated tenant} │                       │
  │<─────────────────────────┤                       │
```

## Tenant deletion flow (with Evolution API cleanup)

```
Master                     FastAPI                  Supabase          Evolution API
  │                          │                       │                    │
  │ DELETE /tenants/{id}     │                       │                    │
  │ (is_active=false)        │                       │                    │
  ├─────────────────────────>│                       │                    │
  │                          │ SELECT profile (get   │                    │
  │                          │  evolution_instance)  │                    │
  │                          ├──────────────────────>│                    │
  │                          │<──────────────────────┤                    │
  │                          │                       │                    │
  │                          │ DELETE FROM users     │                    │
  │                          │  WHERE id={id}        │                    │
  │                          │  (flush, not commit)  │                    │
  │                          ├──────────────────────>│                    │
  │                          │                       │                    │
  │                          │ DELETE /instance/     │                    │
  │                          │  delete/tenant-{name} │                    │
  │                          ├───────────────────────────────────────────>│
  │                          │                       │                    │
  │                          │  ── if Evolution fails ──                 │
  │                          │  db.rollback() ──────>│                    │
  │                          │  return 409           │                    │
  │                          │                       │                    │
  │                          │  ── if Evolution ok ──                    │
  │                          │  db.commit() ────────>│                    │
  │                          │                       │                    │
  │ 204 No Content           │                       │                    │
  │<─────────────────────────┤                       │                    │
```

## Redis HA active-passive failover flow

> **Implemented in:** Redis Session HA phase (2026-05-12).
> See ADR-0004 for the complete decision.

```
                         ┌──────────────────────────────────────────────────┐
                         │           RedisConnectionManager                │
                         │  (process-lifetime pools + FailoverPolicy)     │
                         │                                                  │
                         │  ┌──────────────┐      ┌──────────────┐        │
                         │  │  Primary     │      │  Backup      │        │
                         │  │  (CLOSED)    │      │  (standby)   │        │
                         │  │  redis://    │      │  redis://    │        │
                         │  │  or rediss://│      │  or rediss://│        │
                         │  └──────┬───────┘      └──────┬───────┘        │
                         │         │                     │                │
                         │         │  FailoverPolicy     │                │
                         │         │  ┌─────────────────┐│                │
                         │         │  │ CLOSED (normal) ││                │
                         │         │  │ OPEN (backup)   ││                │
                         │         │  │ HALF_OPEN (probe)││               │
                         │         │  └─────────────────┘│                │
                         └──────────────────────────────────────────────────┘
                                       │
                                       │ execute(operation, callable)
                                       v
                         ┌──────────────────────────────────────────────────┐
                         │        WhatsAppSessionService                    │
                         │  session:{phone} → ConversationSession (JSON)  │
                         │  TTL: 15 minutes (900s, default)                │
                         │  touch_ttl: only on valid flow progress         │
                         │  used_backup: delegated to FailoverPolicy       │
                         └──────────────────────────────────────────────────┘
```

### Normal operation (CLOSED)

```
WhatsAppConsoleService           RedisConnectionManager           Primary Redis
      │                                   │                           │
      │ process_message()                 │                           │
      ├──────────────────────────────────>│                           │
      │                                   │ execute("get_session",_)  │
      │                                   ├──────────────────────────>│
      │                                   │<──────────────────────────┤
      │                                   │ record_success()          │
      │                                   │ (failures reset to 0)     │
      │                                   │                           │
      │                                   │ execute("save_session",_) │
      │                                   ├──────────────────────────>│
      │                                   │<──────────────────────────┤
      │                                   │                           │
      │ reply ← ContingencyReplyPolicy or │                           │
      │        console flow text          │                           │
      │<──────────────────────────────────┤                           │
```

### Failover (breaker OPEN)

```
WhatsAppConsoleService           RedisConnectionManager           Primary Redis      Backup Redis
      │                                   │                           │                │
      │ process_message()                 │                           │                │
      ├──────────────────────────────────>│                           │                │
      │                                   │ execute("get_session",_)  │                │
      │                                   ├──────────────────────────>│                │
      │                                   │<────── ConnectionError ──┤                │
      │                                   │                           │                │
      │                                   │ record_failure()          │                │
      │                                   │ consecutive=1→2→3         │                │
      │                                   │ (threshold=3 → OPEN)     │                │
      │                                   │                           │                │
      │                                   │ execute("get_session",_)  │                │
      │                                   ├──────────────────────────────────────────>│
      │                                   │<──────────────────────────────────────────┤
      │                                   │                           │                │
      │  ── if session found on backup ──                              │                │
      │  reply ← console flow text                                     │                │
      │                                                                                │
      │  ── if session NOT found on backup ──                                          │
      │  create fresh session (for next message)                                       │
      │  reply ← ContingencyReplyPolicy.SESSION_RESET                                  │
      │                                   │                           │                │
```

### Recovery (HALF_OPEN → CLOSED)

```
WhatsAppConsoleService           RedisConnectionManager           Primary Redis
      │                                   │                           │
      │ process_message()                 │                           │
      ├──────────────────────────────────>│                           │
      │                                   │ 30s elapsed after OPEN    │
      │                                   │ state → HALF_OPEN         │
      │                                   │                           │
      │                                   │ execute("get_session",_)  │
      │                                   ├──────────────────────────>│
      │                                   │<────── success ──────────┤
      │                                   │                           │
      │                                   │ record_success()          │
      │                                   │ (CLOSED, back to primary) │
      │                                   │                           │
```

### Both Redis stores unavailable

When both primary and backup Redis are unreachable (or only primary is
configured and it fails), the ``RedisConnectionManager.execute()`` raises
``RedisUnavailableError`` which ``WhatsAppConsoleService`` catches and
returns ``ContingencyReplyPolicy.TEMPORARY_UNAVAILABLE``. The backend never
degrades to stateless operation.

## Phone canonicalization flow

Every incoming phone value follows a deterministic pipeline:

```
n8n / API request → normalize_phone(value)
                          │
                          ├── Strip "+" prefix
                          ├── Strip JID suffix ("@c.us", "@s.whatsapp.net")
                          ├── Strip device suffix (":" + digits)
                          ├── Strip all non-digits (spaces, dashes, parens)
                          │
                          └── Return digits-only string or None
                                │
                                ├── Used for: AuthService.identify_by_phone()
                                ├── Used for: Redis session key ("session:{phone}")
                                └── Stored in: master_profiles.phone / tenant_profiles.phone
```

Applied at every entry point:
- `POST /api/v1/integrations/n8n/identify?phone=` — identifies caller
- `POST /api/v1/integrations/n8n/console` — normalises phone before session lookup
- Pydantic schemas `TenantCreate`, `TenantUpdate` — normalise phone on input
- `AuthService.identify_by_phone()` — normalises before DB lookup
- `WhatsAppSessionService._session_key()` — key is based on canonicalised phone

## Unified login via users table

```
          ┌─────────────┐
          │    users     │
          ├─────────────┤
          │ id (UUID)   │────┐
          │ username    │    │ role=master
          │ password_hash│   │
          │ role         │   ├── master_profiles
          │ created_at  │   │    (id FK, name, phone)
          │ updated_at  │   │
          └─────────────┘   │
                            │ role=tenant
                            ├── tenant_profiles
                            │    (id FK, full_name, email,
                            │     phone, evolution_instance_name,
                            │     is_active)
                            │
                            └── refresh_sessions
                                 (user_id FK, hash, expires, revoked)
```
