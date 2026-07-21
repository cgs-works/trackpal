---
id: tenant-admin.access-control
audience: tenant_admin
plans:
  - starter
  - pro
channels:
  - web
  - whatsapp
module: settings
capabilities:
  - tenant_access_control
route: /admin/settings
help_targets:
  - admin.settings.access-control
title: Control de acceso de WhatsApp
summary: Decide qué personas o números pueden usar TrackPal desde WhatsApp.
search_tags:
  - control de acceso
  - teléfono bloqueado
  - identidad bloqueada
  - desbloquear
  - bloqueo de WhatsApp
synonyms:
  - bloqueo del bot
  - contactos bloqueados
  - denegar acceso
order: 80
safe_navigation:
  route: /admin/settings
  settings_category: access-control
related_topics:
  - tenant-admin.whatsapp
  - tenant-admin.activate-access-code-lookup
  - tenant-admin.profile
tour:
  - release_id: tenant-admin-starter-1
    order: 6
    target: admin.settings.access-control
    conditional: false
    plans:
      - starter
    title: Controla el acceso por WhatsApp
    content: |
      # Controla el acceso por WhatsApp

      Aquí puedes revisar quién está bloqueado, buscar un teléfono y recuperar el acceso cuando sea necesario. Una lista vacía significa que nadie está bloqueado.
---

# Control de acceso de WhatsApp

Usa esta lista para bloquear o recuperar el acceso de una persona al menú de TrackPal en WhatsApp.

En Web, abre **Configuración > Control de acceso** para buscar un teléfono, bloquearlo o quitar un bloqueo. En WhatsApp, abre **Control de acceso** desde el menú de **TrackPal Starter** o **TrackPal Pro**.

Un bloqueo impide usar el bot y pedir códigos de acceso, pero no elimina al cliente ni sus suscripciones. Si la lista está vacía, nadie está bloqueado. Si no encuentras un número, revisa los dígitos o limpia la búsqueda.

Cuando necesites recuperar el acceso, desbloquea exactamente la entrada que aparece en pantalla. Si la identidad no muestra un teléfono reconocible, pide ayuda antes de elegir otra.
