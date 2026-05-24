# Implement plan — services modularization

## Steps

- [ ] Map public methods/consumers for each target service.
- [ ] Split `subscription_service.py` package-first.
- [ ] Split `subscription_job_service.py`.
- [ ] Split `client_service.py`.
- [ ] Split `tenant_service.py`.
- [ ] Split `whatsapp_auth_session_service.py`.
- [ ] Ensure repositories usage for DB access.
- [ ] Run focused tests after each service.

## Validation

```bash
cd backend
uv run pytest -v -k "subscription or tenant or client or auth_session"
uv run pytest -v
```

## Done

- [ ] Target services modularized
- [ ] No scoped module >240 LoC
- [ ] Tests pass
