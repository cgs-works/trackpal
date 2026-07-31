---
id: tenant-admin.public-api
audience: tenant_admin
plans:
  - pro
channels:
  - web
module: settings
capabilities:
  - tenant_catalog
  - tenant_public_api
  - tenant_settings
route: /admin/settings
help_targets:
  - admin.settings.public-api
title: Publicar tu Catálogo en un sitio web
summary: Prepara el Catálogo y entrega a tu desarrollador lo necesario para mostrarlo.
search_tags:
  - API pública
  - Clave API
  - sitios autorizados
  - catálogo en navegador
  - entrega al desarrollador
  - catálogo de solo lectura
  - Cloudflare
synonyms:
  - catálogo para sitio web
  - catálogo externo
  - integración frontend
  - paquete para desarrollador
order: 155
safe_navigation:
  route: /admin/settings
  settings_category: public-api
safe_links:
  - route: /admin/catalog
    settings_category: null
related_topics:
  - tenant-admin.catalog
  - tenant-admin.first-pro-client
tour:
  - release_id: tenant-admin-pro-upgrade-1
    order: 5
    target: admin.settings.public-api
    conditional: false
    plans:
      - pro
    title: Publica tu Catálogo
    content: |
      # Lleva tu Catálogo a tu sitio web

      Prepara los servicios que quieres mostrar, registra tu sitio y entrega a tu desarrollador las instrucciones disponibles en Configuración.
---

# Publicar tu Catálogo en un sitio web

Con **TrackPal Pro** puedes mostrar los servicios y planes de tu Catálogo en tu sitio web. Los visitantes solo pueden consultarlos; no pueden cambiar datos ni ver credenciales.

## Qué debes preparar

1. Revisa que el Catálogo tenga los servicios y planes correctos.
2. En **Configuración > Clave API**, agrega cada sitio autorizado con su dirección exacta, por ejemplo `https://tienda.example.com`.
3. Crea la clave y entrega a tu desarrollador el paquete de instrucciones y la clave por canales separados.

No necesitas programar. El paquete incluye ejemplos para distintas tecnologías y usa `YOUR_PUBLIC_API_KEY` como marcador. Tu desarrollador debe reemplazarlo con la clave real y proteger `GET /api/v1/public/catalog` con rate-limit o WAF de Cloudflare.

## Iconos de servicio en la API pública

Los servicios del Catálogo público incluyen un campo opcional `icon` con una referencia Iconify `prefix:name`. El paquete para desarrollador muestra cómo convertirla en una URL SVG de Iconify. Tu sitio web debe proporcionar un icono de respaldo genérico. Los navegadores de los visitantes contactan Iconify directamente para mostrar los iconos de servicio.

## Si el sitio no muestra el Catálogo

Comprueba que la dirección registrada coincida exactamente con el allowed origin del navegador. Regenerar la clave invalida la anterior; revocarla desactiva el Catálogo público. Nunca publiques la clave en capturas, repositorios o chats abiertos.
