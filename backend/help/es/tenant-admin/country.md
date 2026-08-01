---
id: tenant-admin.country
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
  - admin.settings.regional
title: País
summary: Elige el país donde opera tu negocio.
search_tags:
  - país
  - moneda del país
  - país del negocio
synonyms:
  - ubicación
order: 21
safe_navigation:
  route: /admin/settings
  settings_category: my-account
  tab: regional
related_topics:
  - tenant-admin.currency
  - tenant-admin.language
---

# País

TrackPal almacena el país como un código ISO. Los nombres de los países se muestran en el idioma que elegiste para el espacio de trabajo.

Abre **Mi cuenta > Configuración regional**, selecciona el país y guarda. Elegir un país sitúa su moneda oficial primero en el selector de moneda sin cambiar la moneda guardada.

Este ajuste está disponible en los planes TrackPal Starter y TrackPal Pro.
