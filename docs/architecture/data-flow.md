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

## n8n → Evolution API → WhatsApp flow

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
     │                       │                     │ Route by role         │
     │                       │                     │ Menu router           │
     │                       │                     │                       │
     │                       │                     │ If action=list:       │
     │                       │                     │ GET /tenants          │
     │                       │                     ├──────────────────────>│
     │                       │                     │<──────────────────────┤
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
