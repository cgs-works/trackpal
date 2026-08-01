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
summary: Combina fechas, recordatorios y acciones de ciclo para mantener las suscripciones al día.
search_tags:
  - vencimiento de suscripciones
  - gestión de vencimientos
  - suscripciones por vencer
  - flujo de renovación
  - vencimiento automático
  - días de aviso
synonyms:
  - administración de vencimientos
  - planificación de renovación
  - fechas de fin de suscripción
order: 160
safe_navigation:
  route: /admin/subscriptions
  settings_category: null
safe_links:
  - route: /admin/settings
    settings_category: my-account
    tab: regional
  - route: /admin/settings
    settings_category: reminders
related_topics:
  - tenant-admin.subscriptions
  - tenant-admin.reminders
  - tenant-admin.timezone
---

# Gestionar vencimientos

En **TrackPal Pro**, tres cosas trabajan juntas: la fecha de la suscripción, la zona horaria del negocio y los recordatorios de WhatsApp.

## Antes del vencimiento

Confirma la zona horaria, activa los recordatorios si los deseas y verifica que cada suscripción tenga la fecha y el teléfono de destinatario correctos.

Cuando una suscripción esté por vencer, usa **Renovar** para extenderla. Si ya venció o fue cancelada, usa **Renovar** o **Reactivar** cuando estén disponibles. **Cancelar** termina el acceso antes de la fecha prevista.

En WhatsApp, abre **Suscripciones** desde el menú de **TrackPal Pro**. Las acciones visibles usan `1` Editar, `2` Cancelar, `3` Renovar y `4` Reactivar; `8` avanza, `9` retrocede y `0` cancela.

## Cambios automáticos

Al final del día local, una suscripción vencida pasa a **Expirada**. Después de 7 días puede pasar a **Cancelada**, y después de más de 30 días cancelada se elimina. La automatización de recordatorios es independiente de estos cambios.

Si una fecha parece incorrecta, revisa primero la zona horaria. Si falta un recordatorio, revisa la suscripción, los destinatarios y la conexión de WhatsApp.
