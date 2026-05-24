# Implement plan — API modularization

## Steps

- [ ] Identify route groups in subscriptions endpoint.
- [ ] Split subscriptions endpoint into submodules.
- [ ] Identify integration flow blocks.
- [ ] Split integrations endpoint into submodules.
- [ ] Keep router imports and prefixes stable.
- [ ] Remove duplicated business/query logic from endpoint layer.
- [ ] Run API focused tests.

## Validation

```bash
cd backend
uv run pytest -v -k "subscriptions or integrations or api"
uv run pytest -v
```

## Done

- [ ] Endpoints modularized
- [ ] No scoped module >240 LoC
- [ ] HTTP contracts unchanged
- [ ] Tests pass
