---
id: tenant-admin.subscriptions
audience: tenant_admin
plans:
  - pro
channels:
  - web
  - whatsapp
module: subscriptions
capabilities:
  - tenant_subscriptions
route: /admin/subscriptions
help_targets:
  - admin.subscriptions
title: Suscripciones
summary: Gestiona el acceso de cada cliente a tus servicios y planes.
search_tags:
  - suscripciones
  - suscripciones del cliente
  - filtrar suscripciones
  - crear suscripción
  - cancelar suscripción
  - renovar suscripción
  - reactivar suscripción
  - revelar credenciales
synonyms:
  - membresías
  - planes del cliente
  - acceso al servicio
order: 120
safe_navigation:
  route: /admin/subscriptions
  settings_category: null
related_topics:
  - tenant-admin.clients
  - tenant-admin.catalog
  - tenant-admin.first-pro-client
tour:
  - release_id: tenant-admin-pro-1
    order: 5
    target: admin.subscriptions
    conditional: false
    plans:
      - pro
    title: Suscripciones
    content: |
      # Gestiona las suscripciones

      Conecta cada cliente con un servicio y plan. Aquí puedes revisar fechas y estados, además de renovar, reactivar o cancelar cuando corresponda.
  - release_id: tenant-admin-pro-upgrade-1
    order: 3
    target: admin.subscriptions
    conditional: false
    plans:
      - pro
    title: Suscripciones en TrackPal Pro
    content: |
      # Conoce Suscripciones

      Conecta clientes con servicios y planes, controla sus fechas y gestiona cada etapa del acceso.
---

# Suscripciones

En **TrackPal Pro**, una suscripción conecta un cliente con un servicio y plan del Catálogo. Usa los filtros para buscar por cliente, servicio o estado.

## Crear o editar

Pulsa **Nueva suscripción**, elige cliente, servicio y plan, y completa el correo del servicio. Puedes añadir contraseña, perfil y PIN cuando hagan falta. Elige una duración o una fecha personalizada y revisa el resumen antes de guardar.

Si dejas vacía una contraseña o PIN al editar, TrackPal conserva el valor anterior. Si ya existe una suscripción activa para el mismo cliente, servicio y correo, revisa si conviene extenderla en lugar de duplicarla.

## Estados y acciones

- **Activa:** puede editarse, cancelarse o renovarse.
- **Expirada:** puede renovarse o reactivarse.
- **Cancelada:** puede reactivarse con nuevas fechas.

**Renovar** extiende el vencimiento. **Reactivar** inicia un nuevo período. **Cancelar** cambia el estado sin borrar de inmediato el registro.

En WhatsApp abre **Suscripciones** en el menú de **TrackPal Pro**. Usa `1` Editar, `2` Cancelar, `3` Renovar o `4` Reactivar cuando estén disponibles; `8` avanza, `9` regresa y `0` cancela.

Usa **Revelar credenciales** solo cuando sea necesario y nunca copies contraseñas o PIN en una solicitud de soporte.
