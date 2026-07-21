---
id: tenant-admin.catalog
audience: tenant_admin
plans:
  - pro
channels:
  - web
  - whatsapp
module: catalog
capabilities:
  - tenant_catalog
route: /admin/catalog
help_targets:
  - admin.catalog
title: Catálogo
summary: Organiza los servicios y planes que ofrece tu negocio.
search_tags:
  - catálogo
  - servicio
  - plan
  - crear servicio
  - crear plan
  - renombrar servicio
  - renombrar plan
  - eliminar servicio
  - eliminar plan
  - impacto de eliminación
synonyms:
  - catálogo de productos
  - oferta
  - lista de servicios
order: 110
safe_navigation:
  route: /admin/catalog
  settings_category: null
related_topics:
  - tenant-admin.clients
  - tenant-admin.first-pro-client
  - tenant-admin.subscriptions
tour:
  - release_id: tenant-admin-pro-1
    order: 4
    target: admin.catalog
    conditional: false
    plans:
      - pro
    title: Catálogo
    content: |
      # Prepara tu Catálogo

      Crea los servicios que ofrece tu negocio y añade sus planes. Los usarás al preparar una suscripción para un cliente.
  - release_id: tenant-admin-pro-upgrade-1
    order: 2
    target: admin.catalog
    conditional: false
    plans:
      - pro
    title: Catálogo en TrackPal Pro
    content: |
      # Conoce el Catálogo

      Organiza tus servicios y planes para usarlos al preparar suscripciones.
---

# Catálogo

En **TrackPal Pro**, el Catálogo reúne tus servicios y los planes disponibles para cada uno. Prepáralo antes de crear suscripciones.

## Crear y organizar

Crea un servicio, ábrelo y añade sus planes. También puedes cambiar sus nombres desde Web o desde **Catálogo** en el menú de WhatsApp de **TrackPal Pro**. Una lista vacía solo significa que todavía no has creado el primer servicio o plan.

## Antes de eliminar

TrackPal muestra cuántas suscripciones activas e históricas dependen del servicio o plan. Revísalas con calma: eliminar es irreversible y también elimina las suscripciones asociadas.

En Web escribe `DELETE` para confirmar. En WhatsApp usa `CONFIRM` o `CONFIRMAR`; `0` cancela y `9` regresa.

Si una vista previa no carga o el nombre ya existe, corrige el problema antes de continuar. No necesitas compartir credenciales de clientes para recibir ayuda.
