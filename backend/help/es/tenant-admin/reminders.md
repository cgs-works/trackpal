---
id: tenant-admin.reminders
audience: tenant_admin
plans:
  - pro
channels:
  - web
module: settings
capabilities:
  - tenant_subscriptions
  - tenant_settings
route: /admin/settings
help_targets:
  - admin.settings.reminders
title: Recordatorios de suscripciones
summary: Avisa por WhatsApp antes de que una suscripción llegue a su vencimiento.
search_tags:
  - recordatorios
  - recordatorios de suscripciones
  - días de aviso
  - hora del recordatorio
  - destinatarios
  - mensaje personalizado
  - suscripciones por vencer
synonyms:
  - alertas de vencimiento
  - notificaciones de renovación
  - avisos de expiración
  - opt-in
order: 140
safe_navigation:
  route: /admin/settings
  settings_category: reminders
related_topics:
  - tenant-admin.subscriptions
  - tenant-admin.timezone
  - tenant-admin.subscription-expirations
tour:
  - release_id: tenant-admin-pro-upgrade-1
    order: 4
    target: admin.settings.reminders
    conditional: false
    plans:
      - pro
    title: Recordatorios en TrackPal Pro
    content: |
      # Prepara tus recordatorios

      Elige cuántos días antes quieres avisar, la hora local, los destinatarios y el mensaje que recibirán por WhatsApp.
---

# Recordatorios de suscripciones

Con **TrackPal Pro** puedes enviar avisos automáticos antes del vencimiento de una suscripción. La función comienza desactivada.

## Prepararlos

Abre **Configuración > Recordatorios**, activa la función y elige:

- cuántos días antes quieres avisar, por ejemplo 7, 3 y 1;
- la hora local del envío;
- si recibirán el aviso los administradores, el cliente o ambos;
- el mensaje para cada destinatario.

TrackPal completa datos como `{{client_name}}`, `{{service_name}}`, `{{days}}` y `{{expires_at}}`. Conserva esas etiquetas y usa la vista previa para revisar el resultado.

Los avisos se preparan aproximadamente cada 30 minutos según la zona horaria del negocio. Si no llega uno, revisa que la suscripción esté activa, la fecha sea correcta, WhatsApp esté conectado y el destinatario tenga teléfono.

Guardar la configuración no envía un mensaje inmediato ni cambia el estado de una suscripción.
