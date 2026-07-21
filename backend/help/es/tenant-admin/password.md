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
title: Cambiar tu contraseña
summary: Actualiza la contraseña de la cuenta con la que administras TrackPal.
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

# Cambiar tu contraseña

Abre **Configuración > Contraseña**. Escribe tu contraseña actual, crea una nueva, repítela y guarda.

El cambio solo afecta a la cuenta con la que iniciaste sesión. No modifica las cuentas de otros administradores, clientes, WhatsApp ni el buzón central.

Si TrackPal rechaza el cambio, revisa el mensaje del formulario. Tu contraseña anterior seguirá funcionando hasta que la actualización termine correctamente. Nunca envíes una contraseña a soporte.
