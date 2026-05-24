# Fix i18n admin string and improve tenant subscription WhatsApp flow

## Goal

Migrate hardcoded strings to i18n, adjust interactive navigation (0 cancel, 9 back/next), and paginate subscriptions 8 per page in tenant workflow.

## Requirements

- Migrar label hardcodeado `Contraseña inicial` en panel admin (club clientes) a i18n frontend.
- Texto final visible:
  - ES: `Contraseña`
  - EN: `Password`
- Eliminar hardcodes en flujo WhatsApp tenant suscripciones:
  - Header `📋 Suscripciones`
  - Labels de estado (`Activa`, etc.)
  - Todo debe salir de catálogos i18n WA.
- Flujo WhatsApp debe ser totalmente interactivo en lista filtrada por estatus:
  - `0` siempre cancela/cierra flujo y vuelve a menú principal tenant.
  - Paginación de lista: `8` anterior, `9` siguiente.
  - Ítems por página: **7** (reserva de teclas para navegación y cancelación).
- Mantener comportamiento existente fuera de este alcance.

## Acceptance Criteria

- [ ] En UI admin/club clientes no existe hardcode `Contraseña inicial`; usa key i18n y muestra `Contraseña` (ES) / `Password` (EN).
- [ ] En WA tenant suscripciones no existen hardcodes de título/estado en formatter; usa keys i18n ES/EN.
- [ ] En lista filtrada WA:
  - [ ] `0` cancela sesión/flujo siempre.
  - [ ] `8` navega a página anterior cuando aplica.
  - [ ] `9` navega a página siguiente cuando aplica.
  - [ ] Solo se renderizan opciones numéricas de suscripción válidas por página (1-7).
- [ ] Con >7 suscripciones, paginación funciona sin romper `selection_map` ni selección de detalle.
- [ ] Verificación mínima: tests backend focalizados de flujo tenant subscriptions pasan.

## Notes

- Keep `prd.md` focused on requirements, constraints, and acceptance criteria.
- Lightweight tasks can remain PRD-only.
- For complex tasks, add `design.md` for technical design and `implement.md` for execution planning before `task.py start`.
