---
id: tenant-admin.first-pro-client
audience: tenant_admin
plans:
  - pro
channels:
  - web
  - whatsapp
module: help
capabilities:
  - tenant_catalog
  - tenant_clients
  - tenant_subscriptions
route: /admin/catalog
help_targets: []
title: Configura tu primer Cliente Pro
summary: Sigue el orden seguro desde la preparación del Catálogo hasta la primera suscripción del cliente.
search_tags:
  - primer cliente
  - configuración Pro
  - configurar catálogo
  - primera suscripción
  - orden de preparación
synonyms:
  - comenzar con clientes
  - primer consumidor
  - configuración inicial
order: 130
safe_navigation:
  route: /admin/catalog
  settings_category: null
safe_links:
  - route: /admin/clients
    settings_category: null
  - route: /admin/subscriptions
    settings_category: null
related_topics:
  - tenant-admin.catalog
  - tenant-admin.clients
  - tenant-admin.subscriptions
---

# Configura tu primer cliente

Usa este orden cuando tu negocio esté listo para atender a su primer cliente. La guía es informativa y sus enlaces solo abren módulos autorizados; Help nunca crea registros ni envía un formulario por ti.

## 1. Prepara el Catálogo

Abre Catálogo y crea el servicio que ofreces. Selecciona ese servicio y crea al menos un plan. Si la lista de servicios o planes está vacía, ese es el estado inicial esperado: usa los controles de creación. Comprueba los nombres antes de salir del módulo. Lee la guía de vista previa de eliminación del Catálogo antes de borrar algo.

## 2. Crea el Cliente

Abre Clientes y elige Crear. Escribe el nombre completo, un nombre de usuario local válido, el teléfono opcional y una contraseña. Guarda el formulario y copia para la persona el patrón de inicio de sesión canónico `{client_prefix}_{local_username}`. Busca el nuevo cliente y verifica que su estado sea activo.

Si el usuario local o teléfono ya existe, corrige el valor en vez de repetir datos duplicados. No envíes la contraseña del cliente por un canal inseguro. El cliente solo puede usar el nombre de usuario completo mientras el plan actual incluya acceso para clientes y la cuenta esté activa.

## 3. Abre las suscripciones del Cliente

Desde la fila del Cliente elige la acción de suscripciones, o abre Suscripciones y selecciona el filtro del cliente. Crea la primera suscripción eligiendo el servicio y plan preparados; luego escribe solo las credenciales y fechas requeridas por el formulario. Revisa el resumen antes de confirmar. El topic de Clientes explica el enlace directo; el topic de Catálogo explica los datos que necesita.

## Orden en Web y WhatsApp

En Web los enlaces autorizados son Catálogo, Clientes y Suscripciones. En WhatsApp usa el menú Pro: `2` Catálogo, `1` Clientes y `4` Suscripciones. Dentro de un flujo sigue los mensajes visibles `9` Regresar, `8` Siguiente, `0` Cancelar y las confirmaciones. Una entrada inválida mantiene el flujo en su paso actual; no crea una preparación parcial.

## Finalización y recuperación

La configuración termina cuando el servicio, plan, cliente activo y primera suscripción aparecen en sus respectivos módulos autorizados. Si un módulo carga o no está disponible, reintenta ese módulo y corrige el error de validación visible. Si falla la creación de una suscripción, el Catálogo y Cliente siguen disponibles; comprueba el servicio, plan, estado del cliente y valores del formulario antes de reintentar.

## Límite de soporte

Soporte puede ayudarte a identificar qué requisito falta. Comparte solo nombres de módulos y estados visibles; nunca compartas contraseñas de clientes, credenciales de suscripciones, credenciales del buzón, códigos de acceso ni claves API.
