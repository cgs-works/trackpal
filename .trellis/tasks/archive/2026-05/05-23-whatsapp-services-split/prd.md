# WhatsApp services split

## Goal

Partir servicios/facades WhatsApp de alto tamaño en módulos pequeños, manteniendo flujo conversacional actual sin regresiones.

## Confirmed Facts

- Objetivos >200 LoC:
  - `whatsapp_tenant_console_service.py` (3093)
  - `whatsapp_console_service.py` (1327)
  - `whatsapp_master_console_facade.py` (467)
- Flujos sensibles: estados, transiciones, fallback, comandos reset/help, i18n.

## Requirements

- Convertir cada archivo gigante en paquete por dominio/flow.
- Preservar exactamente comportamiento de routing conversacional.
- Mantener claves i18n y mensajes funcionales.
- Mantener interfaz pública usada por integraciones/API.
- Respetar LoC (`<=200`, max 240 con deuda).

## Dependencies

- Requiere `core-schemas-modularization`.
- Depende de contratos estabilizados de `services-modularization` y `api-modularization`.

## Acceptance Criteria

- [x] WhatsApp servicios/facade divididos en módulos pequeños.
- [x] Sin módulo >240 LoC en alcance.
- [x] Flujos críticos WhatsApp mantienen comportamiento.
- [x] Tests `console/whatsapp` pasan.

## Out of Scope

- Cambios de producto en menús/reglas de negocio.
