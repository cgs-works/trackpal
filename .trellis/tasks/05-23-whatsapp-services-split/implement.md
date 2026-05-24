# Implement plan — WhatsApp services split

## Steps

- [ ] Inventory current flows/states per WhatsApp file.
- [ ] Split `whatsapp_console_service.py` by flow handlers.
- [ ] Split `whatsapp_tenant_console_service.py` by state-machine domains.
- [ ] Split `whatsapp_master_console_facade.py` orchestration/adapters.
- [ ] Preserve entrypoint interfaces.
- [ ] Keep i18n and contingency behavior intact.
- [ ] Run WhatsApp-focused tests after each split block.

## Validation

```bash
cd backend
uv run pytest -v -k "whatsapp or console"
uv run pytest -v
```

## Done

- [ ] WhatsApp modules split under LoC policy
- [ ] Flow behavior unchanged
- [ ] Tests pass
