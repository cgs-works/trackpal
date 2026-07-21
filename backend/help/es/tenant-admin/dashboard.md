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

      Esta orientación es opcional y dura aproximadamente de 2 a 3 minutos. Explica dónde están las herramientas incluidas en tu plan actual y cómo se relacionan el panel web, WhatsApp, las plataformas habilitadas y el buzón central.

      Continúa con **Siguiente** o elige **Omitir recorrido**. Omitirlo nunca bloquea tu panel de control y puedes repetirlo desde Ayuda.
  - release_id: tenant-admin-starter-1
    order: 2
    target: admin.dashboard
    conditional: false
    plans:
      - starter
    title: Dashboard y navegación
    content: |
      # Tu panel de control

      El Dashboard muestra tu plan actual y el estado general de las herramientas. Usa la navegación para moverte entre Dashboard, Configuración y Ayuda. Allí solo aparecen las secciones incluidas en tu plan actual.

      Estos valores son de solo lectura. El recorrido usa la información real de tu negocio y no crea datos de demostración ni cambia configuraciones.
  - release_id: tenant-admin-pro-1
    order: 1
    target: admin.dashboard
    conditional: false
    plans:
      - pro
    title: Bienvenido a TrackPal
    content: |
      # Bienvenido a TrackPal

      Esta orientación es opcional y dura aproximadamente de 2 a 3 minutos. Explica las herramientas incluidas en tu plan y cómo se relacionan el panel web, WhatsApp, las suscripciones, los recordatorios y la publicación de tu catálogo en un sitio web.

      Continúa con **Siguiente** o elige **Omitir recorrido**. Omitirlo nunca bloquea tu panel de control y puedes repetir esta orientación desde Ayuda.
  - release_id: tenant-admin-pro-1
    order: 2
    target: admin.dashboard
    conditional: false
    plans:
      - pro
    title: Dashboard y navegación
    content: |
      # Tu panel de control

      El Dashboard muestra tu plan actual y el estado general de las herramientas. Según tu plan, la navegación también incluye Clientes, Catálogo y Suscripciones. Configuración reúne los ajustes de tu negocio y Ayuda explica cada sección.

      Los valores aquí son de solo lectura. El recorrido usa la información real de tu negocio y no crea datos de demostración ni cambia ajustes.
---

# Dashboard

El Dashboard es el punto de partida de tu panel de control. Resume lo que TrackPal puede hacer para tu negocio según tu plan actual.

## Canal, requisitos y acciones

- **Canal:** Web. El dashboard no es un menú de WhatsApp.
- **Requisitos:** Inicia sesión como administrador con un negocio activo. No necesitas configurar nada para leer la página.
- **Acciones:** Abre Dashboard desde la barra lateral y usa los indicadores de solo lectura para decidir qué módulo abrir después.

## Resultados y estados

- Ves tu plan Starter o Pro, el estado del buzón central de búsqueda, la cantidad de servicios de códigos habilitados y la cantidad de identidades de WhatsApp bloqueadas.
- Pro también muestra clientes activos, servicios del Catálogo, suscripciones activas y suscripciones próximas a vencer.
- Un estado de carga significa que TrackPal está actualizando los datos del negocio. Un buzón vacío o cero servicios habilitados significa que la búsqueda de códigos aún no está lista.
- Si falla la carga, la página queda sin métricas actuales. Reintenta desde la página y contacta a soporte si el error persiste.

## Límites, consecuencias y recuperación

El Dashboard es de solo lectura: verlo no crea registros ni cambia configuraciones. No vincula WhatsApp, habilita plataformas, configura un buzón ni inicia una sesión de WhatsApp. Abre la categoría correspondiente de Configuración para completar la preparación. Si un módulo no aparece en la navegación, el plan actual no lo incluye; los datos Pro se conservan después de bajar a Starter, pero las acciones Pro quedan inactivas.

## Web y WhatsApp

Usa el Dashboard web para consultar el resumen. WhatsApp tiene su propio menú de administrador y reglas de sesión; usa el tema de WhatsApp para ese flujo. Los valores del Dashboard se actualizan con el negocio activo y pueden cambiar después de que otro administrador modifique la configuración.

## Límite de soporte

Soporte puede ayudarte a interpretar un estado, el acceso del plan o un error de carga persistente. No envíes contraseñas, códigos de vinculación, tokens ni credenciales del buzón en una solicitud.
