# Implement plan — repositories migration

## Steps

- [ ] Create `app/repositories` package scaffold.
- [ ] Move `crud/users.py` into `repositories/users_repository.py`.
- [ ] Add temporary `app/crud` shim exports.
- [ ] Extract tenant/client/auth/subscription query blocks from services into repositories.
- [ ] Extract query blocks from `api/dependencies.py` into repositories.
- [ ] Replace service/API imports to repositories.
- [ ] Remove dead query helpers after migration.
- [ ] Run auth/tenant/client/subscription tests.

## Validation

```bash
cd backend
uv run pytest -v -k "auth or tenant or client or dependency or subscription"
uv run pytest -v
```

## Done

- [ ] Repository layer used across migrated domains
- [ ] No functional regression
- [ ] Compatibility shim documented
