# Core and schemas modularization

## Goal

Modularizar `backend/app/core` y `backend/app/schemas` para cumplir estructura tipo FastAPI templates, con módulos pequeños y sin cambios funcionales.

## Confirmed Facts

- Archivos objetivo >200 LoC:
  - `backend/app/core/i18n.py` (926)
  - `backend/app/core/redis_client.py` (503)
  - `backend/app/core/input_validation.py` (413)
  - `backend/app/schemas/subscription.py` (242)

## Requirements

- Refactor solo dominios `core` y `schemas` en esta tarea hija.
- Objetivo por módulo `<=200` LoC; permitido `201-240` solo con deuda explícita.
- Mantener contratos públicos usados por servicios/endpoints/tests.
- No cambiar reglas de negocio ni payloads.
- Preferir paquetes por dominio cuando archivo supere límite.

## Dependencies

- Debe completarse antes de `repositories-migration`, `services-modularization`, `api-modularization` y `whatsapp-services-split`.

## Acceptance Criteria

- [x] Ningún módulo nuevo de `core`/`schemas` supera 240 LoC.
- [x] Excepciones 201-240 quedan documentadas con plan cierre.
- [x] Imports existentes siguen funcionando (o compatibilidad equivalente).
- [x] Tests backend relevantes pasan.

## Out of Scope

- Migración de `crud` a `repositories`.
- Split de servicios/API.
