---
id: tenant-admin.subscriptions
audience: tenant_admin
plans:
  - pro
channels:
  - web
  - whatsapp
module: subscriptions
capabilities:
  - tenant_subscriptions
route: /admin/subscriptions
help_targets:
  - admin.subscriptions
title: Suscripciones de clientes
summary: Abre y gestiona las suscripciones asociadas a un cliente, servicio y plan.
search_tags:
  - suscripciones
  - suscripciones del cliente
  - filtrar suscripciones
  - crear suscripción
  - cancelar suscripción
  - renovar suscripción
  - reactivar suscripción
  - revelar credenciales
synonyms:
  - membresías
  - planes del cliente
  - acceso al servicio
order: 120
safe_navigation:
  route: /admin/subscriptions
  settings_category: null
related_topics:
  - tenant-admin.clients
  - tenant-admin.catalog
  - tenant-admin.first-pro-client
---

# Suscripciones de clientes

Las suscripciones conectan a un Cliente con un servicio y plan del Catálogo. Abre Suscripciones desde la barra lateral o usa la acción de suscripciones en una fila de Clientes para llegar con ese cliente seleccionado.

## Canal, requisitos y acciones

- **Web:** Filtra la lista por estado, servicio o cliente. Crea una suscripción, edita sus campos, cancélala, renuévala, reactiva una suscripción cancelada o abre el diálogo para revelar credenciales cuando exista una razón válida.
- **WhatsApp:** Desde el menú principal Pro elige `4` Suscripciones. Filtra la lista, selecciona una suscripción y usa las acciones mostradas según su estado: editar, cancelar, renovar o reactivar cuando esté disponible.
- **Requisitos:** El Tenant debe ser Pro. Crea el servicio y plan requeridos en Catálogo y ten un Cliente activo antes de crear una suscripción.

## Estados, confirmaciones y datos sensibles

Activa, expirada y cancelada son estados distintos. Cancelar cambia el estado y no elimina la suscripción. Renovar o reactivar cambia las fechas después de una confirmación. Los diálogos de creación y ciclo de vida muestran un resumen antes de modificar; cancela con el botón visible o con `0` en WhatsApp.

Las contraseñas de streaming y los PIN de perfil son credenciales sensibles. Revélalos solo mediante la acción explícita de Web cuando sea necesario, no los pegues en Help ni en soporte y recuerda que un enlace de Help nunca los revela. Una suscripción activa duplicada puede ofrecer extender su vencimiento en lugar de crear otra.

## Estados vacíos, validación y recuperación

Una lista vacía significa que ninguna suscripción coincide con los filtros actuales, no que se haya eliminado el Cliente o el Catálogo. La falta de servicio, plan o Cliente impide crear. Un email, fecha, duración, selección o confirmación inválidos conserva la suscripción existente. Si falla la carga o una modificación, reintenta después de revisar el error visible.

## Límite de soporte

Soporte puede ayudar con un error persistente de suscripción o ciclo de vida usando el estado e identificadores visibles. Nunca compartas contraseñas de streaming, PIN de perfil, credenciales del buzón ni credenciales reveladas.
