# Refactor backend services >200 LoC into smaller modules

## Goal

Reducir tamaño/complexidad de servicios en `backend/app/services/` (solo archivos >200 LoC), separando responsabilidades en módulos más pequeños sin cambiar comportamiento observable.

## Confirmed Facts (repo)

- Skill `fastapi-templates` disponible en `.pi/skills/fastapi-templates/`.
- Backend `app/` tiene **14 archivos >200 LoC**:
  - `services/whatsapp_tenant_console_service.py` (3093)
  - `services/whatsapp_console_service.py` (1327)
  - `core/i18n.py` (926)
  - `services/subscription_service.py` (512)
  - `core/redis_client.py` (503)
  - `services/subscription_job_service.py` (468)
  - `services/whatsapp_master_console_facade.py` (467)
  - `api/v1/endpoints/subscriptions.py` (453)
  - `core/input_validation.py` (413)
  - `api/v1/endpoints/integrations.py` (337)
  - `services/whatsapp_auth_session_service.py` (264)
  - `services/client_service.py` (263)
  - `services/tenant_service.py` (254)
  - `schemas/subscription.py` (242)
- Capa `app/crud/users.py` sí tiene uso real transversal (services + api dependencies + tests).
- Carpeta `app/crud/` contiene solo código útil en `users.py` (`__init__.py` + caches locales no funcionales).

## Requirements

- Alcance actualizado por usuario: refactor **todo backend** (`backend/**`) hacia estructura modular tipo `fastapi-templates`.
- Objetivo de tamaño: target <=200 LoC por módulo, límite duro máximo 240 LoC.
- Mantener API pública/contratos observables (endpoints, respuestas, flujos WhatsApp, auth/sesiones, catálogo, tenant, suscripciones).
- Mantener comportamiento funcional sin regresiones.
- Definir convención estructural final (paquetes por dominio + submódulos).
- Migrar `app/crud/` hacia `app/repositories/` alineado a `fastapi-templates`.
- Verificar/migrar otros archivos que deban pertenecer a capa de acceso a datos.
- Ejecutar de forma incremental, con validación por bloque.

## Acceptance Criteria

- [x] Inventario validado de todos archivos backend >200 LoC con estrategia por archivo.
- [x] Diseño objetivo documentado alineado a `fastapi-templates`.
- [x] Decisión documentada para `app/crud/` y plan de migración/convivencia.
- [x] Todos módulos objetivo quedan <=200 LoC.
- [x] Sin cambios funcionales observables (tests + smoke flows críticos).
- [x] Suite de tests backend relevante pasa después refactor.
- [x] Plan por fases listo (`design.md` + `implement.md`) antes de `task.py start`.

## Out of Scope (provisional)

- Cambios de reglas de negocio.
- Nuevos endpoints o features.
- Reescritura frontend.

## Open Questions

- Estrategia de compatibilidad de imports durante migración (`app.crud` -> `app.repositories`): shim temporal vs corte directo por fase.

## Decisions (confirmed)

- Ejecutar como **parent task + tareas hijas por dominio** para validación incremental y menor riesgo.
- Alcance incluye **todo `backend/**`**.
- Tamaño objetivo por módulo: **<=200 LoC**, tope permitido: **240 LoC**.
- Módulos 201-240 LoC permitidos temporalmente solo con deuda explícita y plan de cierre.
- `app/crud/` se migra a `app/repositories/` en esta iniciativa.
- Migración de acceso a datos será completa ahora: incluir queries directas en `services/` y `api/dependencies.py`.
- Orden de ejecución: `core + schemas` primero.
