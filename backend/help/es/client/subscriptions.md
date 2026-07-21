---
id: client.subscriptions
audience: client
plans:
  - pro
channels:
  - web
  - whatsapp
module: subscriptions
capabilities:
  - client_subscriptions
route: /client/dashboard
help_targets:
  - client.subscriptions
title: Suscripciones activas
summary: Comprende las suscripciones de servicios asignadas a tu cuenta de Cliente.
search_tags:
  - suscripciones
  - servicio
  - plan
  - vencimiento
  - estado
synonyms:
  - membresías
  - planes de acceso
order: 30
safe_navigation:
  route: /client/dashboard
  settings_category: null
related_topics:
  - client.dashboard
  - client.whatsapp
---

# Suscripciones activas

El Dashboard muestra las suscripciones activas que tu proveedor te ha asignado.

## Canal, requisitos y acciones

- **Canales:** Web y WhatsApp. Tu proveedor debe asignar una suscripción a tu cuenta de Cliente activa.
- **Requisitos:** Inicia sesión en Web o entra en la consola de Cliente de WhatsApp cuando tu proveedor la haya habilitado.
- **Acciones:** En Web, consulta el servicio, plan, estado, fecha de inicio y vencimiento. En WhatsApp, elige la opción de suscripciones activas que muestre la consola. Los Clientes no pueden crear, renovar, cancelar ni revelar credenciales de suscripción.

## Resultados y estados

El estado activo, pendiente, vencido o cancelado se muestra sin permitir que el Cliente lo cambie. Una lista vacía significa que no hay asignaciones activas. Si el vencimiento se acerca, puede aparecer una advertencia de días restantes; consulta al proveedor sobre la renovación. Los estados de carga y error pueden reintentarse en Web.

## Límites de Web y WhatsApp

El Dashboard web es la fuente completa para las fechas y la información del proveedor. WhatsApp ofrece un resumen y no modifica las suscripciones. Los cambios de contraseña son exclusivos de Web y se explican en Cambio de contraseña en Web.

## Límite de soporte

El proveedor decide el ciclo de vida de las suscripciones y controla las credenciales de los servicios. Nunca envíes credenciales, códigos de acceso ni capturas de datos privados a soporte.
