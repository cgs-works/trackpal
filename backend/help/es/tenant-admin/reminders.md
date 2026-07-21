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
order: 140
safe_navigation:
  route: /admin/settings
  settings_category: reminders
related_topics:
  - tenant-admin.subscriptions
  - tenant-admin.timezone
  - tenant-admin.subscription-expirations
---

# Ajustes de recordatorios de suscripciones

Los ajustes de recordatorios controlan las notificaciones opcionales de WhatsApp que se preparan cuando una suscripción se acerca a su vencimiento. Los recordatorios son una función opt-in: permanecen desactivados hasta que un Tenant Admin Pro los activa. Es un ajuste de Tenant Pro. No crea, renueva, cancela ni reactiva suscripciones y Help nunca guarda el formulario por ti.

## Activación y requisitos

Abre Ajustes, elige Ajustes de recordatorios de suscripciones y activa el interruptor cuando el Tenant esté listo para usar notificaciones automáticas de vencimiento. Los recordatorios están desactivados por defecto. El Tenant debe ser Pro, la suscripción debe estar activa y los destinatarios necesitan teléfonos de WhatsApp utilizables. Los Tenant Admin Starter no pueden ver, recuperar ni buscar este topic; la automatización no cambia los datos de suscripciones conservados mientras el Tenant sea Starter.

Cuando los recordatorios están desactivados, no se generan payloads pendientes ni registros de recordatorio para el Tenant. Guardar los ajustes no envía un mensaje inmediatamente. El módulo Suscripciones sigue siendo el lugar para las acciones manuales de ciclo de vida.

## Días de aviso y hora local

Elige uno o más días de aviso antes del vencimiento. Los días predeterminados son 7, 3 y 1; puedes quitar un día predeterminado o agregar otro número positivo. Mientras los recordatorios estén activos se necesita al menos un día de aviso.

Configura la hora del recordatorio en la hora local del Tenant. La hora es un umbral: el backend puede preparar el recordatorio de ese día cuando el reloj local alcance la hora configurada. La zona horaria se muestra aquí como referencia y se edita en la categoría separada Zona horaria. Consulta ese topic antes de cambiarla si el negocio opera en otra zona horaria IANA.

El día de aviso se calcula con la fecha del calendario local del Tenant, no tratando cada día como un intervalo UTC fijo. El backend controla la comprobación de hora local, por lo que el horario de transporte de n8n no cambia el significado de la hora configurada.

## Destinatarios y mensajes personalizados

Elige quién recibe un recordatorio elegible:

- **Solo Tenant:** se envía al teléfono de WhatsApp del negocio.
- **Solo Cliente:** se envía al teléfono de WhatsApp del Cliente.
- **Ambos:** prepara un recordatorio para cada destinatario disponible.

El formulario también ofrece campos separados de mensaje personalizado para Tenant y Cliente. Conserva los placeholders admitidos como `{{client_name}}`, `{{service_name}}`, `{{days}}`, `{{streaming_email}}` y `{{expires_at}}` al editarlos. La vista previa reemplaza valores de ejemplo para comprobar el texto antes de guardar; no incluyas contraseñas, secretos del buzón ni códigos de acceso en un mensaje.

Si el destinatario elegido no tiene un teléfono utilizable, ese destinatario se omite. Un guardado fallido deja la configuración anterior. Corrige el error visible de una lista de días vacía o una hora `HH:MM` inválida y vuelve a guardar.

## Automatización y recuperación

El backend evalúa los Tenant Pro, las suscripciones activas, los días de aviso locales, la hora local, los destinatarios y la protección contra duplicados. Un workflow separado de n8n consulta aproximadamente cada 30 minutos, transporta los payloads pendientes a WhatsApp e informa si se entregaron o fallaron. No decide la zona horaria del Tenant ni ejecuta cambios de ciclo de vida.

Un recordatorio puede quedar pendiente, enviado o fallar después de los reintentos. Si no aparece un recordatorio, revisa el plan Pro, el interruptor, el día de aviso, la hora local, Zona horaria, el estado activo, la fecha de vencimiento, el enlace de WhatsApp y el teléfono del destinatario. No desconectes WhatsApp ni reveles credenciales como primera respuesta. La guía de vencimientos conecta estas comprobaciones con la renovación manual, la reactivación, la cancelación y las transiciones automáticas.

## Navegación segura y límite de soporte

El enlace de Help abre Ajustes en la categoría de recordatorios sin guardar, activar, enviar ni cambiar un ajuste. Soporte puede revisar un error persistente de programación o entrega con el estado visible y la hora aproximada. Nunca compartas contraseña de Cliente, contraseña de streaming, PIN de perfil, credenciales del buzón, token OAuth, código de acceso ni secreto de vinculación de WhatsApp.
