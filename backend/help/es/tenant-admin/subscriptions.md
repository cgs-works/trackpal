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
tour:
  - release_id: tenant-admin-pro-1
    order: 5
    target: admin.subscriptions
    conditional: false
    plans:
      - pro
    title: Suscripciones y recordatorios
    content: |
      # Opera las suscripciones

      Suscripciones conecta Clientes con servicios y planes del Catálogo. Revisa estados, fechas, filtros, acciones de ciclo de vida, límites de credenciales y los ajustes separados de recordatorios antes de actuar.

      Este recorrido solo destaca el módulo real. Nunca crea, edita, cancela, renueva, reactiva ni muestra credenciales.
  - release_id: tenant-admin-pro-upgrade-1
    order: 3
    target: admin.subscriptions
    conditional: false
    plans:
      - pro
    title: Tu nuevo módulo Pro de Suscripciones
    content: |
      # Suscripciones ahora está disponible

      Tu upgrade agrega Suscripciones. Usa aquí los datos preparados de Clientes y Catálogo para gestionar el acceso a servicios y las decisiones de ciclo de vida.

      El recorrido es de solo lectura: no crea, edita, cancela, renueva, reactiva ni muestra credenciales.
---

# Suscripciones de clientes

Una suscripción conecta a un Cliente con un servicio y plan del Catálogo. Guarda el email de streaming, los datos opcionales del perfil, las fechas de inicio y vencimiento y un estado de ciclo de vida. Abre Suscripciones desde la barra lateral o usa la acción de suscripciones en una fila de Clientes para llegar con ese Cliente seleccionado.

## Canales, requisitos y filtros de la lista

- **Web:** La página Pro de Suscripciones muestra Cliente, servicio, plan, email de streaming, fechas y estado. Filtra por estado, servicio o Cliente y revisa las fechas y el estado visibles antes de elegir una acción.
- **WhatsApp:** Desde el menú principal Pro elige `4` Suscripciones y luego `1` Ver suscripciones. Elige Activas, Expiradas, Canceladas o Todas, selecciona una fila y sigue las acciones mostradas.
- **Requisitos:** El Tenant debe ser Pro. Para crear se necesita un Cliente activo y un servicio y plan existentes en Catálogo. Un Tenant Admin Starter no puede abrir ni buscar este topic o módulo; los datos Pro conservados no se eliminan al degradar.
- **Resultado esperado:** Una creación o actualización exitosa devuelve la suscripción a la lista con su estado y fechas actuales. Un enlace de Help solo abre esta explicación o la ruta segura del módulo; nunca envía un formulario.

## Crear y editar en Web

Elige Nueva suscripción y selecciona Cliente, servicio y plan. Escribe el email de streaming requerido. La contraseña de streaming es opcional; el nombre y PIN de perfil también, pero el PIN necesita un nombre de perfil. Elige una duración como 1, 3, 6 o 9 meses, 1 año o una fecha de vencimiento personalizada, y revisa las fechas de inicio y vencimiento antes de guardar.

Editar permite cambiar los campos expuestos por el formulario. En modo edición, Cliente, servicio y plan identifican la relación existente; dejar vacíos los campos de contraseña o PIN conserva el valor guardado. Un email, contraseña, perfil, duración o fecha nuevos no se aplican hasta guardar correctamente. Una suscripción activa duplicada para el mismo Cliente, servicio y email de streaming puede avisarte para extender el vencimiento existente en vez de crear otro registro.

## Creación, edición y navegación en WhatsApp

Desde Suscripciones elige `2` Crear suscripción. Selecciona Cliente, servicio y plan, escribe el email de streaming, introduce y confirma opcionalmente la contraseña, elige si agregar nombre y PIN de perfil, selecciona una duración y escribe una fecha personalizada cuando se solicite. El resumen final muestra Cliente, servicio, plan, email, perfil, duración y fechas; escribe `CONFIRMAR` o `CONFIRM` solo después de revisarlo.

Para una fila existente, las acciones son `1` Editar, `2` Cancelar, `3` Renovar y `4` Reactivar cuando el estado lo permite. Editar puede cambiar Cliente, servicio, plan, email de streaming, contraseña de streaming, nombre de perfil o PIN de perfil. Los cambios de contraseña y PIN se solicitan dos veces para confirmarlos. Usa `8` para Siguiente cuando una página lo ofrezca, `9` para Regresar y `0` para Cancelar. Una selección inválida mantiene el flujo en su paso; una sesión expirada no crea una suscripción parcial.

## Estados, duraciones y acciones de ciclo de vida

- **Activa:** La suscripción está utilizable y puede editarse, cancelarse o renovarse. El trabajo de recordatorios solo considera suscripciones activas.
- **Expirada:** La fecha de vencimiento pasó según el cierre de día local del Tenant y la automatización. Puede renovarse o reactivarse desde las acciones disponibles.
- **Cancelada:** Cancelar cambia el estado y registra la hora de cancelación; no elimina inmediatamente la fila. Puede reactivarse con nueva duración y fechas.

Cancelar requiere una confirmación visible en Web o una respuesta `CONFIRM`/`CONFIRMAR` en WhatsApp. Renovar extiende desde el vencimiento actual, mientras Reactivar vuelve a iniciar la suscripción cancelada con una duración o fecha personalizada. Ambas acciones muestran las fechas propuestas antes de confirmar. La expiración automática y la limpieza posterior se explican en Gestiona los vencimientos de suscripciones.

## Credenciales, estados vacíos y recuperación

El email de streaming no es el mismo que el inicio de sesión del Cliente. Usa Revelar credenciales en Web solo cuando exista una razón operativa legítima; el diálogo puede mostrar la contraseña de streaming y el PIN de perfil guardados. El detalle de suscripción en WhatsApp puede incluir la información de acceso guardada para el Tenant Admin autenticado. Help nunca activa Revelar, abre un diálogo de credenciales, copia un secreto ni expone una credencial mediante un enlace de módulo.

Una lista vacía puede significar que ninguna suscripción coincide con los filtros elegidos; no significa que se eliminó el Cliente o Catálogo. La falta de Cliente, servicio o plan impide crear. Un email, fecha, duración, selección o confirmación inválidos dejan el registro sin cambios. Si falla la carga o una modificación, revisa el error visible y reintenta sin enviar credenciales a soporte.

## Límite de soporte

Soporte puede investigar un error persistente de suscripción o ciclo de vida con el estado, fechas e identificadores no sensibles visibles. Nunca compartas contraseñas de streaming, PIN de perfil, contraseñas de Clientes, credenciales del buzón, códigos de acceso ni credenciales reveladas. Usa los topics de Ajustes de recordatorios y Zona horaria para las notificaciones automáticas y las fechas locales.
