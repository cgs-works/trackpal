---
id: tenant-admin.mailbox
audience: tenant_admin
plans:
  - starter
  - pro
channels:
  - web
  - whatsapp
module: settings
capabilities:
  - tenant_mailbox
route: /admin/settings
help_targets:
  - admin.settings.mailbox
title: Buzón central de consultas
summary: Conecta y prueba el buzón que recibe los correos con códigos de acceso.
search_tags:
  - buzón
  - bandeja de entrada
  - OAuth
  - IMAP
  - prueba de conexión
  - correo de código
synonyms:
  - buzón de códigos
  - bandeja central
  - conexión de correo
order: 70
safe_navigation:
  route: /admin/settings
  settings_category: mailbox
related_topics:
  - tenant-admin.activate-access-code-lookup
  - tenant-admin.code-services
  - tenant-admin.whatsapp
---

# Buzón central de consultas

El buzón central de consultas es la bandeja que TrackPal revisa para encontrar correos recientes con códigos de acceso. Es una conexión del negocio, no el buzón personal de un cliente.

## Canal, requisitos y acciones

- **Canal:** Web para configurar, probar la conexión y desconectar; WhatsApp usa el buzón conectado durante la búsqueda de códigos.
- **Requisitos:** Ser Tenant Admin y tener acceso al buzón. Elige OAuth de Google o Microsoft, o proporciona un servidor IMAP personalizado, correo, puerto, SSL y contraseña del buzón.
- **Acciones:** Abre Configuración, elige Buzón central de consultas, conecta con OAuth o guarda el formulario IMAP y usa Probar conexión. El estado debe ser Conectado antes de iniciar una búsqueda.

## Resultados y estados

- **No configurado o desconectado:** No hay un buzón listo; la búsqueda de códigos de WhatsApp se detiene antes de mostrar servicios o informa que el buzón no está configurado.
- **Pendiente:** Una ventana OAuth o una prueba de conexión sigue en curso. Mantén la ventana abierta y espera el resultado en vez de iniciar otra conexión.
- **Conectado:** El buzón completó la configuración de conexión y está disponible para el trabajador de búsqueda.
- **Error:** Una prueba fallida o un error del proveedor deja un estado de error y puede mostrar el último error de conexión. Corrige la configuración y prueba de nuevo.
- **Revocado:** Si el proveedor revoca el permiso OAuth, vuelve a conectar el proveedor. Una conexión revocada no se repara repitiendo una búsqueda de WhatsApp.
- **Tiempo de espera agotado:** Un proveedor o servidor IMAP lento puede agotar el tiempo. Revisa host, puerto, SSL y disponibilidad del proveedor antes de reintentar.

## Acciones en Web y WhatsApp

En Web, OAuth abre una ventana de autorización del proveedor. IMAP guarda la configuración antes de probarla. En WhatsApp, la búsqueda lee el buzón central después de confirmar el correo; nunca pide enviar la contraseña del buzón al bot.

## Límites, consecuencias y recuperación

El Tenant tiene un buzón central. Desconectarlo termina la conexión, elimina los secretos guardados del buzón y deja indisponible la búsqueda de códigos hasta completar una conexión nueva; no elimina las plataformas habilitadas, clientes, suscripciones ni entradas de Control de acceso. Si una prueba falla, corrige la configuración visible y vuelve a probar. Si OAuth fue revocado, reconecta. Nunca desconectes un buzón sano solo para recuperar un código que no aparece; revisa primero la plataforma y el correo.

## Límite de soporte

Soporte puede ayudarte con un error persistente de OAuth, IMAP, revocación o tiempo de espera. Comparte el proveedor, estado, host y puerto cuando corresponda, y la hora aproximada; nunca envíes un token OAuth, contraseña IMAP, contraseña del proveedor ni código de acceso.
