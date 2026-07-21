---
id: tenant-admin.whatsapp
audience: tenant_admin
plans:
  - starter
  - pro
channels:
  - web
  - whatsapp
module: settings
capabilities:
  - tenant_whatsapp
route: /admin/settings
help_targets:
  - admin.settings.whatsapp
title: WhatsApp
summary: Vincula el WhatsApp del negocio y entiende la consola de Tenant Admin.
search_tags:
  - WhatsApp
  - código de vinculación
  - código QR
  - dispositivos vinculados
  - desconectar
synonyms:
  - conexión de WhatsApp
  - vincular teléfono
  - bot
order: 30
safe_navigation:
  route: /admin/settings
  settings_category: whatsapp-link
related_topics:
  - tenant-admin.dashboard
  - tenant-admin.profile
  - tenant-admin.language
---

# WhatsApp

WhatsApp conecta el teléfono del negocio con TrackPal para que el bot de Tenant Admin reciba mensajes de consola y envíe respuestas.

## Canal, requisitos y acciones

- **Canales:** Web para la configuración; WhatsApp para la consola conversacional después de vincularlo.
- **Requisitos:** Sé Tenant Admin, abre Configuración y configura un teléfono en Perfil. Ten el teléfono con WhatsApp disponible durante la vinculación. La búsqueda de códigos también necesita plataformas habilitadas y un buzón central.
- **Acciones:** Abre WhatsApp en Configuración, elige Código de vinculación o Código QR, completa la vinculación en Dispositivos vinculados de WhatsApp y espera el estado Conectado. Usa Desconectar solo cuando quieras terminar la vinculación intencionalmente.

## Resultados y estados

Conectado significa que TrackPal puede usar la instancia vinculada para la consola de Tenant Admin y las notificaciones. Conectando o pendiente significa que la vinculación sigue en curso. Desconectado o sin teléfono significa que la consola no está lista. Si WhatsApp revoca el dispositivo vinculado, la instancia vuelve al estado desconectado y debe vincularse otra vez. Un código de vinculación expira y un código QR puede necesitar actualización. Una vinculación exitosa muestra el estado de la instancia; un intento fallido o expirado conserva la conexión anterior y puede reintentarse.

## Acciones en Web y WhatsApp

En Web, Configuración es el lugar seguro para vincular, actualizar un código QR o revisar el estado. En WhatsApp, sigue el menú que muestra el bot según tu plan. Starter ofrece Perfil, búsqueda de códigos, Control de acceso, Ayuda y Salir. Pro también ofrece Clientes, Catálogo y Suscripciones. Usa `0` para salir o cancelar. El mensaje actual etiqueta `8` y `9` para navegar páginas o regresar a la pantalla anterior; sigue esas etiquetas y no envíes credenciales al bot.

## Límites, consecuencias y recuperación

Solo se usa una instancia configurada del negocio para esta conexión. Desconectar termina la sesión vinculada y pausa las acciones de WhatsApp hasta volver a vincular el teléfono; no elimina clientes, elementos del catálogo ni suscripciones. Si la vinculación expira, genera un código nuevo o actualiza el QR. Si falta el teléfono, vuelve a Perfil. Si una sesión de WhatsApp expira, iníciala de nuevo desde el menú. No desconectes una instancia sana repetidamente para corregir un problema de búsqueda de códigos; revisa primero las plataformas y el buzón.

## Límite de soporte

Soporte puede ayudarte con un error persistente de vinculación, estado o sesión. Comparte el estado de la instancia y la hora aproximada, nunca un código de vinculación, imagen QR, token, contraseña o credencial del buzón.
