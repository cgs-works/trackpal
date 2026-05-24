# API modularization

## Goal

Modularizar endpoints backend grandes y adelgazar capa API para delegar lógica a servicios/repositorios.

## Confirmed Facts

- Endpoints objetivo >200 LoC:
  - `backend/app/api/v1/endpoints/subscriptions.py` (453)
  - `backend/app/api/v1/endpoints/integrations.py` (337)

## Requirements

- Dividir endpoints grandes en submódulos por recurso/operación.
- Mantener rutas, métodos, response models y status codes.
- Delegar lógica no-API a servicios/repositorios.
- Respetar LoC (`<=200`, max 240 con deuda).

## Dependencies

- Requiere `core-schemas-modularization` y `repositories-migration`.
- Coordinación con `services-modularization` para contratos.

## Acceptance Criteria

- [ ] Endpoints objetivo modularizados.
- [ ] Contratos HTTP intactos.
- [ ] Sin módulo >240 LoC en alcance.
- [ ] Tests API relevantes pasan.

## Out of Scope

- Nuevos endpoints/features.