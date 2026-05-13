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

> **Architecture update (Phase 1, 2026-05-12):** For the WhatsApp Master Console, n8n is being simplified to **transport-only**. The flow below is the current/legacy implementation where n8n manages session state and calls CRUD endpoints directly. In the new architecture (Phase 3+), the flow becomes:
>
> `WhatsApp → Evolution API → n8n (parse + identify) → POST /api/v1/integrations/n8n/console → Backend (Redis session + flow logic) → reply text → n8n → Evolution API → WhatsApp`
>
> See ADR-0004 for the complete decision.

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
