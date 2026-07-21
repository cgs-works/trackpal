---
id: tenant-admin.code-services
audience: tenant_admin
plans:
  - starter
  - pro
channels:
  - web
  - whatsapp
module: settings
capabilities:
  - tenant_code_services
route: /admin/settings
help_targets:
  - admin.settings.code-services
title: Plataformas de códigos habilitadas
summary: Elige qué servicios compatibles pueden consultarse para buscar códigos de acceso.
search_tags:
  - servicios de código
  - código de acceso
  - plataforma
  - proveedor
  - servicio habilitado
synonyms:
  - servicios de streaming
  - lista de servicios
  - proveedores de códigos
order: 60
safe_navigation:
  route: /admin/settings
  settings_category: code-services
related_topics:
  - tenant-admin.activate-access-code-lookup
  - tenant-admin.mailbox
  - tenant-admin.dashboard
  - tenant-admin.whatsapp
---

# Plataformas de códigos habilitadas

Las plataformas de códigos habilitadas son los servicios que TrackPal puede consultar cuando un Tenant Admin o un cliente solicita un código de acceso. La lista disponible depende del catálogo de plataformas y de la selección de tu Tenant.

## Canal, requisitos y acciones

- **Canal:** Web para configurar; WhatsApp para usar las plataformas seleccionadas en la búsqueda de códigos.
- **Requisitos:** Ser Tenant Admin. La instancia de WhatsApp del negocio y el buzón central son requisitos separados para completar una búsqueda.
- **Acciones:** Abre Configuración, elige Plataformas de códigos habilitadas, selecciona los servicios que deben estar disponibles y guarda. Solo puedes seleccionar servicios activos globalmente.

## Resultados y estados

- **Cargando:** TrackPal está obteniendo la lista de plataformas. Espera a que aparezca antes de cambiar selecciones.
- **Habilitado:** Un servicio seleccionado y activo globalmente aparece en la lista de servicios de WhatsApp.
- **No disponible:** Una plataforma marcada como inactiva globalmente no se puede seleccionar. No es un error de la configuración de tu Tenant.
- **Faltante:** Si no seleccionas ninguna plataforma, la búsqueda de códigos no puede iniciar y WhatsApp informa que los servicios de códigos no están configurados.
- **Error:** Si falla la carga o el guardado, conserva la selección actual, reintenta desde Configuración y no inicies búsquedas repetidas hasta que la lista esté disponible.

## Acciones en Web y WhatsApp

En Web, seleccionar una plataforma cambia los servicios que aparecerán en búsquedas futuras; no consulta el buzón ni envía mensajes de WhatsApp. En WhatsApp, el menú Starter abre la búsqueda con `2` y el menú Pro con `7`. La lista solo contiene la selección efectiva: servicios elegidos por el Tenant que siguen activos globalmente.

## Límites, consecuencias y recuperación

La lista está limitada a los servicios que TrackPal admite y que están activos globalmente. Habilitar una plataforma no conecta una cuenta del proveedor ni crea un cliente o una suscripción. Si una plataforma pasa a estar inactiva globalmente, se omite de las búsquedas hasta que vuelva a estar disponible. Si la búsqueda informa que no hay servicios configurados, vuelve a esta categoría, selecciona una plataforma disponible, guarda e inicia una búsqueda nueva.

## Límite de soporte

Soporte puede confirmar si una plataforma está disponible globalmente e investigar un error persistente de carga o guardado. Comparte solo la etiqueta de la plataforma y el error visible; nunca envíes credenciales del buzón, códigos de acceso, contraseñas ni tokens.
