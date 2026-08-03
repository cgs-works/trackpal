---
id: tenant-admin.profile
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
  - admin.settings.profile
title: Perfil del negocio
summary: Mantén actualizados el nombre, el correo y el teléfono de tu negocio.
search_tags:
  - perfil
  - nombre
  - email
  - teléfono
  - teléfono de WhatsApp
synonyms:
  - datos de cuenta
  - información del negocio
order: 40
safe_navigation:
  route: /admin/settings
  settings_category: my-account
related_topics:
  - tenant-admin.dashboard
  - tenant-admin.language
  - tenant-admin.whatsapp
tour:
  - release_id: tenant-admin-starter-1
    order: 3
    target: admin.settings.profile
    conditional: false
    plans:
      - starter
    title: Configura tu negocio
    content: |
      # Configura tu negocio

      En Perfil mantienes actualizados el nombre y teléfono del negocio. Desde Configuración también puedes cambiar el idioma y tu contraseña.
---

# Perfil del negocio

Aquí guardas el nombre, el correo y el teléfono que TrackPal usa para identificar tu negocio.

Abre **Configuración > Mi cuenta > Perfil**, corrige los datos necesarios y pulsa **Guardar perfil**. El teléfono debe pertenecer al negocio y seguir el formato indicado, porque también puede usarse al preparar WhatsApp.

Si aparece un error, corrige el campo señalado y vuelve a guardar. Recargar la página antes de guardar puede descartar tus cambios.
