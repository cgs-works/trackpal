# Implement plan — core/schemas modularization

## Steps

- [ ] Audit exact public symbols used from oversized core/schemas files.
- [ ] Split `core/i18n.py` into package submodules.
- [ ] Split `core/redis_client.py` into package submodules.
- [ ] Split `core/input_validation.py` into package submodules.
- [ ] Split `schemas/subscription.py` by model group.
- [ ] Add re-exports to preserve current imports.
- [ ] Run focused tests + full backend tests.
- [ ] Record debt entries for any 201-240 module.

## Validation

```bash
cd backend
uv run pytest -v -k "i18n or validation or redis or subscription"
uv run pytest -v
```

## Done

- [ ] No scoped module >240 LoC
- [ ] Tests pass
- [ ] Compatibility preserved
