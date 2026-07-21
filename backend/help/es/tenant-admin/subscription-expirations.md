---
id: tenant-admin.subscription-expirations
audience: tenant_admin
plans:
  - pro
channels:
  - web
  - whatsapp
module: help
capabilities:
  - tenant_subscriptions
  - tenant_settings
route: /admin/subscriptions
help_targets: []
title: Gestionar vencimientos
summary: Combina fechas, recordatorios y acciones para mantener tus suscripciones al día.
search_tags:
  - vencimientos de suscripciones
  - gestión de expiraciones
  - suscripciones por vencer
  - flujo de renovación
  - expiración automática
  - días de aviso
synonyms:
  - gestión de vencimientos
  - planificación de renovaciones
  - fechas finales de suscripción
order: 160
safe_navigation:
  route: /admin/subscriptions
  settings_category: null
safe_links:
  - route: /admin/settings
    settings_category: timezone
  - route: /admin/settings
    settings_category: reminders
related_topics:
  - tenant-admin.subscriptions
  - tenant-admin.reminders
  - tenant-admin.timezone
---

# Gestionar vencimientos

En **TrackPal Pro**, tres elementos trabajan juntos: la fecha de la suscripción, la zona horaria del negocio y los recordatorios de WhatsApp.

## Antes del vencimiento

Confirma la zona horaria, activa los recordatorios si quieres usarlos y revisa que cada suscripción tenga la fecha y el teléfono correctos.

Cuando una suscripción esté por vencer, usa **Renovar** para extenderla. Si ya expiró o fue cancelada, usa **Renovar** o **Reactivar** según la opción disponible. **Cancelar** termina el acceso antes de la fecha prevista.

En WhatsApp abre **Suscripciones** en el menú de **TrackPal Pro**. Las acciones visibles usan `1` Editar, `2` Cancelar, `3` Renovar y `4` Reactivar; `8` avanza, `9` regresa y `0` cancela.

## Cambios automáticos

Al terminar el día local, una suscripción vencida pasa a **Expirada**. Después de 7 días puede pasar a **Cancelada** y, tras más de 30 días cancelada, se elimina. Los recordatorios son independientes de estos cambios.

Si una fecha parece incorrecta, revisa primero la zona horaria. Si falta un aviso, comprueba la suscripción, los destinatarios y la conexión de WhatsApp.
