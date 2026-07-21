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
title: Ajustes de recordatorios de suscripciones
summary: Activa los recordatorios de vencimiento y elige cuándo, dónde y cómo se preparan.
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
    title: Recordatorios y zona horaria Pro
    content: |
      # Nueva automatización Pro

      Tu upgrade agrega recordatorios opcionales de suscripciones y los controles de zona horaria Pro que utilizan. Revisa los ajustes y la guía de vencimientos antes de activar la automatización.

      El recorrido solo abre la vista segura de ajustes. Nunca activa recordatorios, guarda días de aviso, envía mensajes ni cambia el ciclo de vida de una suscripción.
---

# Ajustes de recordatorios de suscripciones

Los ajustes de recordatorios controlan las notificaciones opcionales de WhatsApp para suscripciones próximas a vencer. Tú decides si quieres activar esta función y solo aparece cuando los recordatorios están incluidos en el plan actual. Activarla no crea, renueva, cancela ni reactiva suscripciones, y Ayuda nunca guarda el formulario por ti.

## Activación y requisitos

Abre Configuración, elige Ajustes de recordatorios de suscripciones y activa los recordatorios cuando el negocio esté listo para usar avisos automáticos de vencimiento. Están desactivados por defecto. El plan actual debe incluir recordatorios, la suscripción debe estar activa y cada destinatario necesita un teléfono de WhatsApp válido. Cambiar a un plan sin recordatorios detiene los nuevos avisos, pero no elimina los datos guardados de las suscripciones.

Cuando los recordatorios están desactivados, TrackPal no prepara ni envía nuevos mensajes de recordatorio para el negocio. Guardar los ajustes no envía un mensaje inmediatamente. El módulo Suscripciones sigue siendo el lugar para las acciones manuales de ciclo de vida.

## Días de aviso y hora local

Elige uno o más días de aviso antes del vencimiento. Los días predeterminados son 7, 3 y 1; puedes quitar un día predeterminado o agregar otro número positivo. Mientras los recordatorios estén activos se necesita al menos un día de aviso.

Configura la hora del recordatorio según la hora local del negocio. TrackPal puede preparar el aviso del día cuando el reloj local alcanza la hora elegida. La zona horaria aparece aquí como referencia y se cambia en la sección independiente Zona horaria.

El día de aviso se calcula con la fecha local del negocio. TrackPal controla este horario automáticamente para que la hora seleccionada conserve el mismo significado para tu negocio.

## Destinatarios y mensajes personalizados

Elige quién recibe un recordatorio elegible:

- **Solo administradores:** se envía al teléfono de WhatsApp del negocio.
- **Solo Cliente:** se envía al teléfono de WhatsApp del Cliente.
- **Ambos:** prepara un recordatorio para cada destinatario disponible.

El formulario ofrece mensajes personalizados separados para administradores y clientes. Las palabras entre llaves dobles, como `{{client_name}}`, `{{service_name}}`, `{{days}}`, `{{streaming_email}}` y `{{expires_at}}`, son datos que TrackPal completa automáticamente; no las cambies ni las elimines. Usa la vista previa para revisar el texto y nunca incluyas contraseñas ni códigos de acceso.

Si el destinatario elegido no tiene un teléfono utilizable, ese destinatario se omite. Un guardado fallido deja la configuración anterior. Corrige el error visible de una lista de días vacía o una hora `HH:MM` inválida y vuelve a guardar.

## Automatización y recuperación

TrackPal revisa aproximadamente cada 30 minutos las suscripciones activas que necesitan un recordatorio. Usa los días de aviso, la hora local, los destinatarios y la protección contra duplicados, y luego informa si WhatsApp entregó el mensaje. Esta automatización no cambia el estado ni las fechas de la suscripción.

Un recordatorio puede quedar pendiente, enviado o fallar después de los reintentos. Si no aparece un recordatorio, revisa el plan Pro, el interruptor, el día de aviso, la hora local, Zona horaria, el estado activo, la fecha de vencimiento, el enlace de WhatsApp y el teléfono del destinatario. No desconectes WhatsApp ni reveles credenciales como primera respuesta. La guía de vencimientos conecta estas comprobaciones con la renovación manual, la reactivación, la cancelación y las transiciones automáticas.

## Navegación segura y límite de soporte

El enlace de Help abre Ajustes en la categoría de recordatorios sin guardar, activar, enviar ni cambiar un ajuste. Soporte puede revisar un error persistente de programación o entrega con el estado visible y la hora aproximada. Nunca compartas contraseña de Cliente, contraseña de streaming, PIN de perfil, credenciales del buzón, token OAuth, código de acceso ni secreto de vinculación de WhatsApp.
