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

# Buzón central para códigos

TrackPal revisa este buzón cuando alguien solicita un código de acceso desde WhatsApp. Usa una cuenta administrada por tu negocio, no el correo personal de un cliente.

## Elige cómo conectarlo

- **Google o Microsoft:** conexión guiada. Autoriza el acceso en la ventana del proveedor sin escribir tu contraseña en TrackPal. Esta opción usa OAuth.
- **IMAP:** configuración manual para otros proveedores o para quien prefiera introducir los datos de conexión. Puedes elegir IMAP como alternativa a OAuth.

Después de conectar la cuenta, pulsa **Probar conexión**. Continúa cuando el estado sea **Conectado**.

## Si la conexión falla

Revisa el mensaje visible y vuelve a probar. Si el permiso de Google o Microsoft venció, conecta la cuenta de nuevo. Con IMAP, confirma los datos entregados por tu proveedor de correo. Desconecta el buzón solo si realmente quieres reemplazarlo, porque la búsqueda quedará pausada hasta completar una conexión nueva.
