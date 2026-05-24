# Repositories migration

## Goal

Migrar capa de acceso a datos desde `app/crud` y queries directas dispersas hacia `app/repositories`, alineado con FastAPI templates.

## Confirmed Facts

- `app/crud` contiene código útil en `backend/app/crud/users.py`.
- Uso actual de `user_crud` en `services`, `api/dependencies.py`, `api/v1/endpoints/integrations.py`, tests.
- Hay muchas queries directas en `services/*` y `api/dependencies.py`.

## Requirements

- Crear `backend/app/repositories/` por dominio.
- Migrar lógica de `crud/users.py` a repositorios.
- Extraer queries SQL directas de `services` y `api/dependencies.py` hacia repositorios.
- Mantener shim temporal de compatibilidad para imports antiguos (`app/crud`).
- No cambiar comportamiento funcional.
- Respetar política LoC (`<=200`, max 240 con deuda).

## Dependencies

- Requiere base de contratos de `core-schemas-modularization`.
- Debe completarse antes de `services-modularization` y `api-modularization` final.

## Acceptance Criteria

- [x] `app/repositories` creada y usada por dominios actuales.
- [x] `crud/users.py` migrado.
- [x] Queries seleccionadas migradas fuera de `services`/`api dependencies`.
- [x] Compatibilidad temporal de imports documentada.
- [x] Tests auth/tenant/client pasan.

## Out of Scope

- Split profundo de servicios WhatsApp.
