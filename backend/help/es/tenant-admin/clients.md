---
id: tenant-admin.clients
audience: tenant_admin
plans:
  - pro
channels:
  - web
  - whatsapp
module: clients
capabilities:
  - tenant_clients
route: /admin/clients
help_targets:
  - admin.clients
title: Clientes
summary: Crea y administra las cuentas de las personas que reciben tus servicios.
search_tags:
  - clientes
  - buscar cliente
  - crear cliente
  - editar cliente
  - activar cliente
  - desactivar cliente
  - eliminar cliente
  - inicio canónico
  - suscripciones del cliente
synonyms:
  - usuarios
  - cuentas de clientes
  - consumidores
order: 100
safe_navigation:
  route: /admin/clients
  settings_category: null
related_topics:
  - tenant-admin.first-pro-client
  - tenant-admin.subscriptions
  - tenant-admin.whatsapp
tour:
  - release_id: tenant-admin-pro-1
    order: 3
    target: admin.clients
    conditional: false
    plans:
      - pro
    title: Clientes
    content: |
      # Organiza tus clientes

      Crea una cuenta para cada persona que recibe tus servicios. Desde aquí puedes buscarla, actualizar su acceso y abrir sus suscripciones.
  - release_id: tenant-admin-pro-upgrade-1
    order: 1
    target: admin.clients
    conditional: false
    plans:
      - pro
    title: Clientes en TrackPal Pro
    content: |
      # Conoce Clientes

      Ahora puedes crear cuentas para las personas que reciben tus servicios, gestionar su acceso y abrir sus suscripciones.
---

# Clientes

Con **TrackPal Pro** puedes crear una cuenta para cada persona que recibe tus servicios y gestionar su acceso desde Web o WhatsApp.

## Añadir un cliente

Pulsa **Crear cliente** y completa el nombre, un usuario local, una contraseña de al menos seis caracteres y, si lo tienes, el teléfono. TrackPal añadirá el prefijo de tu negocio al usuario. Entrega al cliente el nombre completo que aparece al guardar, por ejemplo `t1_pepe`.

## Gestionar su acceso

Busca por nombre, usuario o teléfono. Desde cada cliente puedes editar sus datos, desactivar o reactivar el acceso, abrir sus suscripciones y eliminar la cuenta cuando esté inactiva. Desactivar cierra sus sesiones; reactivar le permite iniciar sesión otra vez.

En WhatsApp abre **Clientes** desde el menú de **TrackPal Pro**. Usa `9` para regresar y `0` para cancelar el flujo actual.

Si un usuario o teléfono ya existe, corrige el dato señalado. Eliminar una cuenta es permanente, así que confirma el nombre antes de continuar.
