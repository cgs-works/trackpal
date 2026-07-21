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
summary: Crea y organiza servicios y planes antes de asignar suscripciones a clientes.
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
    title: Servicios y planes del Catálogo
    content: |
      # Prepara el Catálogo

      Catálogo es el lugar donde organizas servicios y planes Pro antes de asignar suscripciones. Revisa la lista y el grupo de acciones seguras; una eliminación siempre tiene una vista previa del impacto y una confirmación fuera de este recorrido.

      El recorrido solo destaca el módulo real. Nunca crea, renombra, elimina ni abre una confirmación destructiva.
  - release_id: tenant-admin-pro-upgrade-1
    order: 2
    target: admin.catalog
    conditional: false
    plans:
      - pro
    title: Tu nuevo Catálogo Pro
    content: |
      # Catálogo ahora está disponible

      Tu upgrade agrega Catálogo. Prepara aquí los servicios y planes antes de asignar suscripciones a los Clientes.

      El recorrido es de solo lectura: no crea, renombra, elimina ni muestra una vista previa destructiva.
---

# Catálogo

El Catálogo contiene los servicios y planes que ofrece tu negocio cuando esta función está incluida en tu plan actual. Un servicio es la oferta y sus planes son las variantes que se seleccionan al crear una suscripción.

## Canal, requisitos y acciones

- **Web:** Abre Catálogo desde la barra lateral. Crea un servicio, selecciónalo, crea o renombra sus planes, renombra un servicio o abre la vista previa de eliminación antes de borrar un servicio o plan.
- **WhatsApp:** Desde el menú principal Pro elige `2` Catálogo. Con servicios, elige `1` para verlos, `2` para crear un servicio o `3` para eliminar un servicio. Selecciona un servicio para editar su nombre, ver planes, crear un plan o eliminar un plan. Sin servicios, el menú ofrece directamente crear el primero.
- **Requisitos:** Catálogo es solo Pro. Para crear un plan, primero crea o selecciona su servicio. Un cambio del catálogo no crea automáticamente un cliente ni una suscripción.

## Servicios, planes y estados vacíos

Un servicio puede existir sin planes. La pantalla de detalle muestra el estado de planes vacío y ofrece Crear plan; regresa con `9` o cancela con `0`. Una lista de servicios vacía significa que no existen servicios, así que crea el primero. Una lista de planes vacía significa que el servicio seleccionado no tiene planes; no es un fallo de carga.

Las listas pueden tener varias páginas. Usa `8` solo cuando se muestre Siguiente y `9` para regresar. Un estado de carga significa que TrackPal está obteniendo el catálogo actual. Un error de carga o guardado conserva el catálogo anterior; reintenta después de revisar el error visible.

## Crear y renombrar

Escribe un nombre de servicio o plan que no esté vacío y guarda en Web, o responde al mensaje de WhatsApp. Un resultado exitoso muestra un mensaje posterior; elige `1` para volver al menú principal. Un nombre vacío, selección inválida, nombre duplicado o servicio no disponible se rechaza y se puede corregir sin crear un registro parcial. Renombrar cambia solo la etiqueta; no mueve planes ni modifica suscripciones existentes.

## Vista previa y consecuencias de eliminar

Eliminar un servicio o plan es irreversible. Antes de confirmar, Web y WhatsApp muestran la vista previa del impacto. Para un servicio revisa la cantidad de planes afectados, suscripciones activas, suscripciones históricas, total de suscripciones y las filas de suscripciones activas. Para un plan revisa las cantidades de suscripciones activas, históricas y totales, además de sus filas. Las suscripciones históricas aparecen en el resumen aunque ya no estén activas.

Eliminar un servicio borra permanentemente ese servicio, sus planes y todas las suscripciones asociadas. Eliminar un plan borra permanentemente ese plan y todas sus suscripciones asociadas. Las suscripciones activas no se conservan ni se convierten. Comprueba los datos de cliente, servicio, plan y vencimiento antes de continuar.

En Web escribe `DELETE` en el campo de confirmación de la vista previa. En WhatsApp escribe `CONFIRM` o `CONFIRMAR` cuando se solicite. Cualquier otro valor muestra otro mensaje de confirmación; `0` cancela y `9` regresa a la selección. Una vista previa cancelada o una eliminación fallida no modifica el catálogo.

## Límites, validación y recuperación

Solo los servicios globalmente activos pueden seleccionarse para la búsqueda de códigos; los nombres del Catálogo no habilitan una plataforma de códigos. El Catálogo no revela credenciales de suscripciones. Si la vista previa no carga, no adivines el impacto ni repitas la acción destructiva; reintenta la vista previa y contacta a soporte con el error visible.

## Límite de soporte

Soporte puede investigar un error persistente de carga, validación, vista previa o eliminación del catálogo. Comparte solo el nombre del servicio o plan y las cantidades visibles; nunca compartas contraseñas de suscripciones, PIN, credenciales del buzón ni códigos de acceso.
