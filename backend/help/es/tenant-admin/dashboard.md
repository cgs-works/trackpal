---
id: tenant-admin.dashboard
audience: tenant_admin
plans:
  - starter
  - pro
channels:
  - web
module: dashboard
capabilities:
  - tenant_dashboard
route: /admin/dashboard
help_targets:
  - admin.dashboard
title: Panel del negocio
summary: Consulta tu plan, el estado operativo y los servicios disponibles para tu negocio.
search_tags:
  - panel
  - plan
  - buzón
  - control de acceso
synonyms:
  - inicio
  - resumen
order: 10
safe_navigation:
  route: /admin/dashboard
  settings_category: null
related_topics:
  - tenant-admin.language
  - tenant-admin.whatsapp
tour:
  - release_id: tenant-admin-starter-1
    order: 1
    target: admin.dashboard
    conditional: false
    plans:
      - starter
    title: Bienvenido a TrackPal
    content: |
      # Bienvenido a TrackPal

      Esta orientación Starter es opcional y dura aproximadamente de 2 a 3 minutos. Explica dónde están las herramientas de tu plan actual y cómo se relacionan Web, WhatsApp, las plataformas habilitadas y el buzón central.

      Continúa con **Siguiente** o elige **Omitir recorrido**. Omitirlo nunca bloquea tu espacio de trabajo y puedes repetirlo desde Ayuda.
  - release_id: tenant-admin-starter-1
    order: 2
    target: admin.dashboard
    conditional: false
    plans:
      - starter
    title: Dashboard y navegación
    content: |
      # Tu espacio Starter

      El Dashboard muestra tu plan actual y las señales operativas. Usa la navegación para moverte entre Dashboard, Configuración y Ayuda. Starter muestra los módulos incluidos en tu plan actual.

      Estos valores son de solo lectura. El recorrido usa tu espacio real y no crea datos de demostración ni cambia configuraciones.
  - release_id: tenant-admin-pro-1
    order: 1
    target: admin.dashboard
    conditional: false
    plans:
      - pro
    title: Bienvenido a Pro
    content: |
      # Bienvenido a Pro

      Esta orientación Pro es opcional y dura aproximadamente de 2 a 3 minutos. Explica los módulos Pro y cómo se relacionan Web, WhatsApp, las suscripciones, los recordatorios y la API pública.

      Continúa con **Siguiente** o elige **Omitir recorrido**. Omitirlo nunca bloquea tu espacio y puedes repetir esta orientación desde Ayuda.
  - release_id: tenant-admin-pro-1
    order: 2
    target: admin.dashboard
    conditional: false
    plans:
      - pro
    title: Dashboard y navegación Pro
    content: |
      # Tu espacio Pro

      El Dashboard muestra tu plan actual y las señales operativas. Pro agrega Clientes, Catálogo y Suscripciones a la navegación, mientras Configuración y Ayuda siguen siendo los puntos seguros para configurar y obtener orientación.

      Los valores aquí son de solo lectura. El recorrido usa tu espacio real y no crea datos de demostración ni cambia ajustes.
---

# Dashboard de la empresa

El Dashboard de la empresa es el punto de partida para los Tenant Admins. Resume lo que TrackPal puede hacer para tu negocio según el plan actual.

## Canal, requisitos y acciones

- **Canal:** Web. El dashboard no es un menú de WhatsApp.
- **Requisitos:** Inicia sesión como Tenant Admin con un Tenant activo. No necesitas configurar nada para leer la página.
- **Acciones:** Abre Dashboard desde la barra lateral y usa los indicadores de solo lectura para decidir qué módulo abrir después.

## Resultados y estados

- Ves tu plan Starter o Pro, el estado del buzón central de búsqueda, la cantidad de servicios de códigos habilitados y la cantidad de identidades de WhatsApp bloqueadas.
- Pro también muestra clientes activos, servicios del Catálogo, suscripciones activas y suscripciones próximas a vencer.
- Un estado de carga significa que TrackPal está actualizando los datos del Tenant. Un buzón vacío o cero servicios habilitados significa que la búsqueda de códigos aún no está lista.
- Si falla la carga, la página queda sin métricas actuales. Reintenta desde la página y contacta a soporte si el error persiste.

## Límites, consecuencias y recuperación

El Dashboard es de solo lectura: verlo no crea registros ni cambia configuraciones. No vincula WhatsApp, habilita plataformas, configura un buzón ni inicia una sesión de WhatsApp. Abre la categoría correspondiente de Configuración para completar la preparación. Si un módulo no aparece en la navegación, el plan actual no lo incluye; los datos Pro se conservan después de bajar a Starter, pero las acciones Pro quedan inactivas.

## Web y WhatsApp

Usa el Dashboard web para consultar el resumen. WhatsApp tiene su propio menú de Tenant Admin y reglas de sesión; usa el tema de WhatsApp para ese flujo. Los valores del Dashboard se actualizan con el Tenant activo y pueden cambiar después de que otro administrador modifique la configuración.

## Límite de soporte

Soporte puede ayudarte a interpretar un estado, el acceso del plan o un error de carga persistente. No envíes contraseñas, códigos de vinculación, tokens ni credenciales del buzón en una solicitud.
