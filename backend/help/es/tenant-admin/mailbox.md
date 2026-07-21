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
  - revocado
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
- **Requisitos:** Tener acceso al correo que usará el negocio. La opción de Google o Microsoft te guía para autorizar el acceso sin escribir la contraseña en TrackPal; esta opción aparece como OAuth. Si prefieres configurar el correo manualmente o usas otro proveedor, puedes elegir IMAP como alternativa. En ese caso necesitarás los datos de conexión que proporciona tu servicio de correo.
- **Acciones:** Abre Configuración y elige Buzón central de consultas. Selecciona Google o Microsoft para una conexión guiada, o IMAP para una conexión manual. Después usa Probar conexión. El estado debe ser Conectado antes de iniciar una búsqueda.

## Resultados y estados

- **No configurado o desconectado:** No hay un buzón listo; la búsqueda de códigos de WhatsApp se detiene antes de mostrar servicios o informa que el buzón no está configurado.
- **Pendiente:** Una ventana de autorización o una prueba de conexión sigue en curso. Mantén la ventana abierta y espera el resultado en vez de iniciar otra conexión.
- **Conectado:** TrackPal puede consultar el buzón cuando alguien solicita un código de acceso.
- **Error:** Una prueba fallida o un error del proveedor deja un estado de error y puede mostrar el último error de conexión. Corrige la configuración y prueba de nuevo.
- **Permiso vencido o retirado:** Si Google o Microsoft retira el permiso, vuelve a conectar la cuenta. Repetir una búsqueda de WhatsApp no repara la conexión.
- **Tiempo de espera agotado:** El servicio de correo tardó demasiado en responder. Si usas IMAP, revisa los datos de conexión y el tipo de seguridad antes de reintentar.

## Acciones en Web y WhatsApp

En Web, la opción de Google o Microsoft abre una ventana segura para autorizar a TrackPal. IMAP es la alternativa manual: debes completar los datos de conexión y guardarlos antes de probarlos. En WhatsApp, la búsqueda consulta el buzón central después de confirmar el correo; nunca pide enviar la contraseña del buzón al bot.

## Límites, consecuencias y recuperación

El negocio tiene un buzón central. Desconectarlo termina la conexión, elimina los secretos guardados del buzón y deja indisponible la búsqueda de códigos hasta completar una conexión nueva; no elimina las plataformas habilitadas, clientes, suscripciones ni entradas de Control de acceso. Si una prueba falla, corrige la configuración visible y vuelve a probar. Si Google o Microsoft retira el permiso, vuelve a conectar la cuenta. Nunca desconectes un buzón sano solo para recuperar un código que no aparece; revisa primero la plataforma y el correo.

## Límite de soporte

Soporte puede ayudarte con un error persistente de autorización, conexión manual o tiempo de espera. Comparte el proveedor, el estado visible y la hora aproximada del error; nunca envíes contraseñas, códigos de autorización ni códigos de acceso.
