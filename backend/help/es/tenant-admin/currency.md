---
id: tenant-admin.currency
audience: tenant_admin
plans:
  - pro
channels:
  - web
module: settings
capabilities:
  - tenant_settings
route: /admin/settings
help_targets:
  - admin.settings.regional
title: Moneda
summary: Expresa los precios de tu catálogo en la moneda de tu negocio.
search_tags:
  - moneda
  - visualización de precios
  - precio del plan
synonyms:
  - unidad monetaria
order: 22
safe_navigation:
  route: /admin/settings
  settings_category: my-account
  tab: regional
related_topics:
  - tenant-admin.country
  - tenant-admin.catalog
---

# Moneda

Este ajuste está disponible en TrackPal Pro.

Abre **Mi cuenta > Configuración regional** y elige la moneda que mejor represente a tu negocio. La moneda oficial del país seleccionado aparece primero encima de un separador en el selector de moneda.

El símbolo de moneda proviene del catálogo incluido (por ejemplo, "Bs." para Venezuela). Los precios de los planes en TrackPal se muestran con este símbolo. Si un plan no tiene precio asignado, el catálogo muestra "Precio a consultar."

Puedes asignar un precio al plan desde el editor de catálogo en Web o desde la consola de WhatsApp.
