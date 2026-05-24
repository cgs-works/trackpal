# Services modularization

## Goal

Dividir servicios backend no-WhatsApp en módulos pequeños por responsabilidad, preservando contratos y comportamiento.

## Confirmed Facts

- Servicios objetivo >200 LoC (no WhatsApp heavy):
  - `subscription_service.py` (512)
  - `subscription_job_service.py` (468)
  - `client_service.py` (263)
  - `tenant_service.py` (254)
  - `whatsapp_auth_session_service.py` (264) [infra sesión]

## Requirements

- Convertir archivos grandes a paquetes/módulos por responsabilidad.
- Mover acceso a datos a `repositories` cuando aplique.
- Mantener métodos públicos y efectos funcionales.
- Mantener límites LoC (`<=200`, max 240 con deuda).

## Dependencies

- Requiere `core-schemas-modularization`.
- Requiere avance de `repositories-migration` para evitar duplicar queries.
- Debe completar antes de cierre global.

## Acceptance Criteria

- [ ] Servicios objetivo divididos en módulos pequeños.
- [ ] Sin cambios de contrato externo.
- [ ] Sin módulo >240 LoC en alcance.
- [ ] Tests de servicios/subscriptions/client/tenant pasan.

## Out of Scope

- `whatsapp_console_service.py`, `whatsapp_tenant_console_service.py`, `whatsapp_master_console_facade.py` (otra tarea hija).