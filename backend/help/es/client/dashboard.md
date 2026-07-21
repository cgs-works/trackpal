---
id: client.dashboard
audience: client
plans:
  - pro
channels:
  - web
module: dashboard
capabilities:
  - client_dashboard
route: /client/dashboard
help_targets:
  - client.dashboard
title: Dashboard de cliente
summary: Consulta tu proveedor, el estado de tu cuenta y el resumen de tus suscripciones activas.
search_tags:
  - dashboard
  - inicio
  - proveedor
  - cuenta
synonyms:
  - página de inicio
  - resumen
order: 10
safe_navigation:
  route: /client/dashboard
  settings_category: null
related_topics:
  - client.profile
  - client.subscriptions
  - client.password
  - client.whatsapp
---

# Dashboard de cliente

El Dashboard de cliente es el punto de inicio de solo lectura para tu cuenta de TrackPal con un proveedor Pro.

## Canal, requisitos y acciones

- **Canal:** Web. Inicia sesión con la cuenta de Cliente creada por tu proveedor.
- **Requisitos:** El plan de TrackPal de tu proveedor debe incluir acceso para clientes y tu cuenta debe estar activa.
- **Acciones:** Abre el Dashboard para consultar tu nombre, proveedor, cuenta y suscripciones activas. La página no modifica los datos del Cliente.

## Resultados y estados

El resumen muestra el nombre del proveedor y el número de suscripciones disponibles. La lista muestra cada servicio, plan, estado, fecha de inicio y vencimiento. Una lista vacía significa que tu proveedor todavía no te ha asignado una suscripción activa.

Cargando significa que TrackPal está consultando los datos actuales. Si la página no carga, usa Reintentar. Una cuenta inactiva o un proveedor que cambió a Starter no puede usar la sesión de Cliente; contacta al proveedor en lugar de crear otra cuenta.

## Web y WhatsApp

Usa el Dashboard web para consultar el resumen completo de solo lectura. WhatsApp tiene una consola de Cliente separada para perfil, suscripciones activas, búsqueda de códigos de acceso y salida. WhatsApp no permite cambiar la contraseña del Cliente.

## Límite de soporte

Tu proveedor controla tu acceso y tus suscripciones. Soporte puede investigar un error persistente de carga o inicio de sesión, pero nunca envíes una contraseña, código de acceso, credencial de suscripción o mensaje privado de WhatsApp.
