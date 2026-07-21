---
id: tenant-admin.help
audience: tenant_admin
plans:
  - starter
  - pro
channels:
  - web
module: help
capabilities:
  - tenant_settings
route: /admin/help
help_targets:
  - admin.help
title: Ayuda
summary: Encuentra respuestas y repite el recorrido cuando lo necesites.
search_tags:
  - ayuda
  - manual
  - orientación
  - repetir recorrido
synonyms:
  - guía
  - instrucciones
  - recorrido
order: 170
safe_navigation:
  route: /admin/help
  settings_category: null
related_topics:
  - tenant-admin.dashboard
  - tenant-admin.whatsapp
  - tenant-admin.activate-access-code-lookup
tour:
  - release_id: tenant-admin-starter-1
    order: 7
    target: admin.help
    conditional: false
    plans:
      - starter
    title: Ayuda siempre a mano
    content: |
      # Ayuda siempre a mano

      Busca aquí cualquier tarea o problema relacionado con TrackPal Starter. También puedes repetir esta orientación cuando quieras.
  - release_id: tenant-admin-pro-1
    order: 7
    target: admin.help
    conditional: false
    plans:
      - pro
    title: Ayuda siempre a mano
    content: |
      # Ayuda siempre a mano

      Busca aquí instrucciones para cualquier sección de TrackPal Pro. También puedes repetir esta orientación cuando quieras.
---

# Ayuda

Usa el buscador para escribir una tarea, una pantalla o un problema. TrackPal mostrará únicamente los temas disponibles para tu plan.

Si quieres volver a conocer la aplicación, pulsa **Repetir recorrido de orientación**. Puedes cerrar el recorrido y retomarlo más adelante desde esta misma página.
