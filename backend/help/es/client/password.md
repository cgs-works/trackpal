---
id: client.password
audience: client
plans:
  - pro
channels:
  - web
module: password
capabilities:
  - client_password
route: /client/profile
help_targets:
  - client.password
title: Cambio de contraseña en Web
summary: Cambia la contraseña de inicio de sesión de Cliente desde la página Perfil web.
search_tags:
  - contraseña
  - seguridad
  - inicio de sesión
  - credenciales
synonyms:
  - cambiar acceso
  - restablecer contraseña
order: 40
safe_navigation:
  route: /client/profile
  settings_category: null
related_topics:
  - client.profile
  - client.whatsapp
---

# Cambio de contraseña en Web

Los cambios de contraseña del Cliente están disponibles únicamente en la página Perfil web.

## Canal, requisitos y acciones

- **Canal:** Solo Web. La consola de Cliente de WhatsApp nunca cambia una contraseña.
- **Requisitos:** Inicia sesión con una cuenta de Cliente Pro activa, abre Perfil y conoce la contraseña actual. La nueva contraseña debe tener al menos ocho caracteres y la confirmación debe coincidir.
- **Acciones:** Escribe la contraseña actual, escribe y confirma la nueva, y elige Actualizar contraseña. TrackPal valida los campos antes de aplicar el cambio.

## Resultados y recuperación

Una actualización correcta confirma el cambio y limpia el formulario. Un campo vacío, una contraseña corta, una confirmación distinta o una contraseña actual incorrecta dejan la contraseña anterior sin cambios. Si falla la solicitud, revisa el error visible y reintenta. No intentes cambiar la contraseña desde WhatsApp.

## Consecuencias y seguridad

El cambio afecta tu cuenta de inicio de sesión web de Cliente. No modifica tu perfil, suscripciones, datos del proveedor, sesión de WhatsApp ni credenciales de servicios. Elige una contraseña única y no la compartas con el proveedor ni con soporte.

## Límite de soporte

Soporte puede explicar un error visible de validación, pero no puede ver, restablecer ni aceptar tu contraseña. Si no puedes verificar la contraseña actual, contacta al proveedor por su canal habilitado.
