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
title: Buzón central para códigos
summary: Conecta el correo donde recibes los mensajes con códigos de acceso.
search_tags:
  - buzón
  - bandeja de entrada
  - Gmail
  - Google
  - prueba de conexión
  - correo de código
  - contraseña de aplicación
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

# Buzón central para códigos

TrackPal revisa este buzón cuando alguien solicita un código de acceso desde WhatsApp. Usa una cuenta administrada por tu negocio, no el correo personal de un cliente.

## Conecta tu bandeja de Gmail

1. Ve a [Contraseñas de aplicación](https://myaccount.google.com/apppasswords) y asegúrate de que la **Verificación en dos pasos** esté activada en tu cuenta de Google.
2. Si la Verificación en dos pasos no está activada, sigue la guía de Google en [Ayuda de Verificación en dos pasos](https://support.google.com/accounts/answer/185833) para activarla primero.
3. En la página de Contraseñas de aplicación, selecciona **Correo** como la aplicación y **Otra (Nombre personalizado)** como el dispositivo. Ingresa un nombre como "TrackPal" y haz clic en **Generar**.
4. Copia la contraseña de 16 caracteres que aparece.
5. En TrackPal, ve a **Configuración > Buzón** y selecciona **Conexión de Google**.
6. Ingresa tu dirección de Gmail y pega la contraseña de aplicación que generaste.
7. Haz clic en **Probar conexión**. Cuando el estado muestre **Conectado**, tu buzón está listo.

## Elegibilidad para contraseñas de aplicación

Solo puedes generar una contraseña de aplicación cuando la **Verificación en dos pasos** esté activada en tu cuenta de Google. Si no ves la opción de Contraseñas de aplicación, activa primero la Verificación en dos pasos.

## Notas importantes de seguridad

- **No uses tu contraseña normal de Gmail.** Siempre usa una contraseña de aplicación para la conexión.
- Si cambias la contraseña de tu cuenta de Google, la contraseña de aplicación se revoca automáticamente. Necesitarás generar una nueva y reconectar.
- Si pierdes el acceso, genera una nueva contraseña de aplicación en [Contraseñas de aplicación](https://myaccount.google.com/apppasswords) y actualiza la conexión en TrackPal.

## Si la conexión falla

Revisa el mensaje visible y vuelve a probar. Asegúrate de estar usando una contraseña de aplicación, no tu contraseña regular. Si la conexión funcionaba antes y se detuvo, verifica si se cambió la contraseña de tu cuenta de Google — esto revoca todas las contraseñas de aplicación.
