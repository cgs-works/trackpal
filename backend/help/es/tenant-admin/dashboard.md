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
title: Dashboard
summary: Mira el estado de tu negocio y encuentra rápidamente qué necesita atención.
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
    title: Bienvenido a TrackPal Starter
    content: |
      # Conoce TrackPal Starter

      En menos de tres minutos verás dónde están las herramientas principales de tu negocio y cómo se conectan Dashboard, Configuración, WhatsApp y Ayuda.

      Pulsa **Siguiente** para comenzar. Puedes repetir esta orientación cuando quieras desde Ayuda.
  - release_id: tenant-admin-starter-1
    order: 2
    target: admin.dashboard
    conditional: false
    plans:
      - starter
    title: Tu Dashboard
    content: |
      # Empieza en el Dashboard

      Aquí puedes revisar el estado del buzón central, las plataformas habilitadas y el Control de acceso. Usa la barra lateral para abrir Configuración o Ayuda.
  - release_id: tenant-admin-pro-1
    order: 1
    target: admin.dashboard
    conditional: false
    plans:
      - pro
    title: Bienvenido a TrackPal Pro
    content: |
      # Conoce TrackPal Pro

      En menos de tres minutos recorrerás las herramientas que conectan clientes, Catálogo, suscripciones, Configuración y WhatsApp.

      Pulsa **Siguiente** para comenzar. Puedes repetir esta orientación cuando quieras desde Ayuda.
  - release_id: tenant-admin-pro-1
    order: 2
    target: admin.dashboard
    conditional: false
    plans:
      - pro
    title: Tu Dashboard
    content: |
      # Empieza en el Dashboard

      Aquí tienes un resumen de clientes, servicios, suscripciones, próximos vencimientos y herramientas de configuración. Usa la barra lateral para entrar a cada sección.
---

# Dashboard

El Dashboard te da una vista rápida de tu negocio en TrackPal.

## Qué verás

Todas las cuentas muestran el estado del buzón central, las plataformas habilitadas y los accesos de WhatsApp bloqueados. Con **TrackPal Pro** también verás clientes, servicios del Catálogo, suscripciones activas y próximos vencimientos.

Usa estos datos para decidir tu siguiente paso: completar una configuración, atender una suscripción o revisar una integración.

## Si algo no cuadra

Un valor en cero puede ser correcto si todavía no has configurado esa función. Si la página no carga, inténtalo de nuevo. Si el error continúa, comparte con soporte el mensaje visible, no contraseñas ni códigos.
