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
summary: Gestiona clientes Pro, su acceso, estado, inicio de sesión canónico y suscripciones.
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
---

# Clientes

Los clientes son las personas que reciben los servicios ofrecidos por un Tenant Pro. La gestión de clientes está disponible solo para Tenant Admins Pro en Web y en la consola de WhatsApp Pro.

## Canal, requisitos y acciones

- **Web:** Abre Clientes desde la barra lateral. Busca por nombre completo, usuario canónico o teléfono; usa Crear para agregar un cliente, la acción de editar para cambiar sus datos de identidad, el botón de estado para activar o desactivar el acceso, la acción de suscripciones para abrir las suscripciones de ese cliente y la acción de eliminar para un cliente inactivo.
- **WhatsApp:** Desde el menú principal Pro elige `1` Clientes. Elige `1` para ver clientes o `2` para crear uno. Selecciona un cliente para editarlo, desactivarlo, reactivarlo o eliminarlo. Usa `9` para regresar y `0` para cancelar.
- **Requisitos:** El Tenant debe tener plan Pro y tú debes ser su Tenant Admin. Para crear un cliente prepara un nombre completo, un nombre de usuario local válido, una contraseña de al menos seis caracteres y un teléfono opcional.

## Crear e inicio de sesión canónico

Escribe el nombre completo, el nombre de usuario local, el teléfono opcional y la contraseña; luego guarda en Web o confirma el resumen en WhatsApp. El nombre de usuario local debe comenzar con una letra minúscula y contener solo letras minúsculas, números y guiones bajos. TrackPal lo combina con el prefijo inmutable del Tenant para crear el inicio de sesión canónico con la forma `{client_prefix}_{local_username}`, por ejemplo `t1_pepe`. Entrega al cliente ese inicio de sesión completo, no solo la parte local.

Una creación exitosa agrega un cliente activo. Un nombre de usuario local, usuario canónico o teléfono duplicado se rechaza y deja sin cambios a los clientes existentes. Corrige el campo y vuelve a intentarlo. Un nombre, usuario, teléfono o contraseña ausente o inválido es un error de validación; no crea un cliente parcial.

## Buscar, editar, activar y desactivar

La búsqueda es un filtro local sobre la lista cargada y no cambia datos. Una lista vacía significa que no existen clientes; un resultado vacío significa que el filtro no coincide. Limpia la búsqueda o corrige las letras y dígitos.

Editar cambia el nombre completo, el nombre de usuario local o el teléfono. Al cambiar el nombre de usuario local también se actualiza el inicio de sesión canónico. Un valor duplicado o campo inválido se rechaza sin aplicar la edición. Activar restaura el acceso de un cliente inactivo. Desactivar cambia el cliente a inactivo y revoca sus sesiones Web activas; después de reactivarlo, el cliente debe iniciar sesión otra vez.

## Suscripciones y eliminación

Usa la acción de tarjeta o suscripciones de la fila del cliente para abrir Suscripciones filtradas por ese cliente. Es un enlace de navegación seguro: no crea, revela, cancela, renueva ni reactiva una suscripción. El topic de Clientes también se relaciona con el módulo Suscripciones para consultar el flujo completo.

Un cliente activo no se puede eliminar. Primero desactívalo. Eliminar es permanente: borra la cuenta del cliente y su inicio de sesión, no se puede deshacer y no reemplaza la desactivación. Confirma solo después de comprobar que seleccionaste al cliente correcto. Cancelar el diálogo o un error de la solicitud deja al cliente en su estado anterior.

## Validación y recuperación en WhatsApp

El flujo de WhatsApp valida cada campo solicitado y repite el mensaje cuando hay una selección inválida, nombre vacío, usuario vacío, contraseña corta o teléfono inválido. En la confirmación escribe `CONFIRM` o `CONFIRMAR` como se muestre; escribe `0` para cancelar. Un error al crear, editar, activar, desactivar o eliminar conserva los datos anteriores y permite reintentar. `9` regresa a la pantalla anterior y `8` avanza solo cuando el mensaje lo muestra.

## Límite de soporte

Soporte puede ayudar con un error persistente de validación o acceso si compartes el campo y mensaje visibles. Nunca compartas en un ticket o chat la contraseña del cliente, una contraseña generada, un token ni credenciales de suscripciones.
