---
id: tenant-admin.password
audience: tenant_admin
plans:
  - starter
  - pro
channels:
  - web
module: settings
capabilities:
  - tenant_settings
route: /admin/settings
help_targets:
  - admin.settings.password
title: Contraseña
summary: Cambia la contraseña de la cuenta Tenant Admin sin cambiar el perfil del negocio.
search_tags:
  - contraseña
  - seguridad
  - iniciar sesión
  - seguridad de cuenta
synonyms:
  - restablecer contraseña
  - credenciales
order: 50
safe_navigation:
  route: /admin/settings
  settings_category: password
related_topics:
  - tenant-admin.profile
  - tenant-admin.language
---

# Contraseña

Usa Contraseña en Configuración para cambiar la contraseña de la cuenta Tenant Admin con la que iniciaste sesión.

## Canal, requisitos y acciones

- **Canal:** Web. Los cambios de contraseña no están disponibles en la consola de WhatsApp del Tenant Admin.
- **Requisitos:** Inicia sesión con la cuenta cuya contraseña quieres cambiar y abre Configuración, luego Contraseña. Necesitas la contraseña actual.
- **Acciones:** Escribe la contraseña actual, una nueva contraseña, confírmala y guarda. TrackPal valida el nuevo valor antes de enviarlo.

## Resultados y estados

Un cambio exitoso confirma la actualización. Mientras guarda, el formulario está ocupado. Los valores faltantes, incorrectos o que no coinciden muestran un error de validación y no cambian la contraseña. Si falla la solicitud, la contraseña existente sigue siendo válida y puedes reintentar desde el formulario.

## Límites, consecuencias y recuperación

Cambiar la contraseña afecta esta cuenta Tenant Admin, no a otros administradores, clientes, credenciales del buzón ni sesiones de WhatsApp. Usa una contraseña nueva que cumpla el mínimo mostrado por el formulario y no reutilices la contraseña de un buzón compartido. Si olvidaste la contraseña actual o fallan varios intentos, deja de probar y usa la recuperación disponible o contacta al propietario del espacio; no reveles la contraseña a soporte.

## Límite de soporte

Soporte puede explicar un error visible de validación o conexión, pero no puede ver, recuperar ni aceptar una contraseña. Nunca incluyas contraseñas actuales o nuevas en un ticket, chat, captura o búsqueda de Ayuda.
