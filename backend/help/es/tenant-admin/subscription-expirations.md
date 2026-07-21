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
title: Gestiona los vencimientos de suscripciones
summary: Conecta fechas locales, recordatorios, acciones manuales de ciclo de vida y transiciones automáticas.
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

# Gestiona los vencimientos de suscripciones

La gestión de vencimientos conecta tres secciones incluidas con las suscripciones: Suscripciones para acciones manuales, Zona horaria para el calendario local del negocio y Ajustes de recordatorios para los mensajes opcionales de WhatsApp. Esta guía es informativa. Sus enlaces solo abren pantallas seguras; Help nunca crea, edita, cancela, renueva, reactiva, revela ni elimina una suscripción.

## Preparar el calendario operativo

1. Abre Zona horaria y confirma la región que corresponde a la ubicación del negocio. TrackPal la usa para fechas locales, umbrales de recordatorios y el límite de final de día de la limpieza.
2. Abre Ajustes de recordatorios de suscripciones y decide si activarlos. Si los activas, elige días de aviso como 7, 3 y 1, define la hora local, selecciona Administradores, Clientes o Ambos y revisa los datos que TrackPal completará en el mensaje personalizado.
3. Abre Suscripciones y revisa Cliente, servicio, plan, estado, fecha de inicio, fecha de vencimiento y email guardado. El plan actual debe incluir la gestión de suscripciones para que estas herramientas estén disponibles.

Los enlaces de zona horaria y recordatorios son navegación segura: seleccionan una categoría de Ajustes, pero no guardan un formulario ni envían un mensaje. Un enlace de Help a Suscripciones no abre un diálogo para revelar credenciales.

## Respuesta manual al vencimiento en Web o WhatsApp

Para una suscripción activa próxima a vencer, revisa las fechas y elige Renovar. Selecciona una duración disponible o una fecha personalizada, lee el nuevo vencimiento propuesto y confirma. Si cambió la relación del servicio o las credenciales, usa Editar por separado y guarda solo después de comprobar el resumen del formulario.

Si una suscripción está Expirada, renuévala o reactívala según la acción disponible y la decisión del negocio. Reactivar la inicia de nuevo con nuevas fechas; renovar extiende desde el vencimiento actual. Si el acceso debe terminar antes, Cancelar cambia el estado a Cancelada sin borrar inmediatamente la fila. Cancelar y las acciones de ciclo de vida requieren la confirmación visible en Web o `CONFIRM`/`CONFIRMAR` en WhatsApp.

En WhatsApp usa el menú Pro `4`, elige el filtro de estado, selecciona la suscripción y usa `1` Editar, `2` Cancelar, `3` Renovar o `4` Reactivar cuando aparezca. Usa `8` Siguiente, `9` Regresar y `0` Cancelar según el mensaje actual. Nunca pegues un secreto en un enlace de Help ni en un mensaje de confirmación.

## Transiciones y recordatorios automáticos

Cuando los recordatorios están activos, TrackPal revisa las suscripciones activas usando la fecha y la hora local del negocio. Prepara un mensaje para cada destinatario elegido y evita duplicados para la misma suscripción y día. La revisión ocurre aproximadamente cada 30 minutos e informa si WhatsApp entregó cada mensaje.

Los cambios automáticos de estado son independientes del envío de recordatorios. Al terminar el día local del negocio, una suscripción cuya fecha ya pasó cambia a Expirada. Después de al menos 7 días pasa automáticamente a Cancelada y, tras más de 30 días en ese estado, se elimina. Ayuda y los mensajes de recordatorio nunca ejecutan estos cambios por sí mismos.

Desactivar los recordatorios detiene los nuevos mensajes, pero no pausa ni elimina suscripciones. Cambiar a un plan sin gestión de suscripciones conserva la información mientras estos procesos automáticos permanecen pausados. Los datos vuelven a estar disponibles si el negocio regresa a un plan compatible, según su estado y fechas actuales.

## Estados de vencimiento y recuperación

- Sin recordatorio: revisa acceso Pro, interruptor, días de aviso, hora local, zona horaria, estado activo, teléfono del destinatario y disponibilidad de WhatsApp.
- Fecha inesperada: confirma la zona IANA y distingue el instante de vencimiento guardado de su representación en el calendario local.
- Expirada pero necesaria: revisa el registro y usa Renovar o Reactivar; no crees un duplicado sin comprobar Cliente, servicio y email existentes.
- Cancelada por automatización: confirma si se esperaba la transición después de siete días expirada y si aún existe una ruta de recuperación manual compatible.
- Entrega fallida: revisa el estado pendiente o fallido y el error visible; no alternes repetidamente los ajustes ni reveles credenciales como solución.

## Seguridad y límite de soporte

Revelar credenciales es una acción sensible separada de Web y esta guía nunca la abre. No incluyas contraseñas de streaming, PIN de perfil, contraseñas de Clientes, credenciales del buzón, códigos de acceso, claves API ni secretos de vinculación de WhatsApp en búsquedas de Help o solicitudes de soporte. Soporte puede usar identificadores no sensibles, estados, fechas, plan, zona horaria, destinatarios y horas aproximadas para investigar un problema persistente.
