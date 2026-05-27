# Implementation Plan — LID/JID resolution

## Ordered Checklist

1. Evolution-go
- Update chatbot payload in `pkg/webhook/service/listener.go`:
  - include `senderPn`, `senderLid`.
- Reuse current message info normalization/swap logic from `whatsmeow.go`.
- Validate payload example with local log/output.

2. n8n workflow
- Edit `n8n/Trackpal WhatsApp Bot.json` Parse Input node:
  - derive `phone` from `senderPn` first.
  - if LID-only, send `sender_lid` and keep `phone` empty/null.
  - preserve original `remoteJid` for outbound Evolution reply target.
- Keep current instance/message/session mapping untouched.
3. Backend schema
- Alembic migration: add nullable `whatsapp_lid` + indexes on:
  - `master_profiles`
  - `tenants`
  - `clients`

4. Backend models/schemas
- Add fields in SQLAlchemy models.
- Extend WhatsApp console request schema with optional LID field.

5. Backend lookup logic
- Add repository queries by `whatsapp_lid`.
- Update `AuthService.identify_by_phone` path or add `identify_by_contact` wrapper:
  - phone-first
  - LID fallback
- Update `integrations/console.py` including `_route_by_instance` to consume fallback for tenant/client/ambiguity branches.
- Implement progressive fill: when phone match happens and payload includes `sender_lid`, persist/update `whatsapp_lid` in matched entity.
6. Tests
- Update/add endpoint tests in `backend/tests/test_whatsapp_endpoint.py`:
  - `@s.whatsapp.net` still passes.
  - `@lid` + `senderPn` resolves.
  - `@lid` without `senderPn`, with persisted `whatsapp_lid`, resolves.
  - `@lid` unknown returns unknown-access reply.
  - instance-first routing resolves by LID for tenant/client paths.
  - ambiguity branch behavior with LID is deterministic.
- Add/adjust phone normalizer tests to assert `@lid` is not accepted as canonical phone path.
- Add test for progressive fill (LID saved when `senderPn` + `senderLid` provided).
## Validation Commands

```bash
cd backend
uv run pytest tests/test_whatsapp_endpoint.py -q
uv run pytest tests/test_phone_normalizer.py -q
```

If migration/model changes broad:

```bash
uv run pytest -q
```

## Risky Files

- `backend/app/api/v1/endpoints/integrations/console.py`
- `backend/app/services/auth_service/service.py`
- `backend/app/repositories/users_repository.py`
- `backend/app/core/phone.py`
- `backend/app/core/input_validation/phone_utils.py`
- `n8n/Trackpal WhatsApp Bot.json`
- `evolution-go/pkg/webhook/service/listener.go`

## Rollback Points

- Revert migration + model fields if LID strategy changes.
- Keep payload backward compatible by only adding fields, not removing existing keys.
