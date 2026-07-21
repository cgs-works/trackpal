---
id: tenant-admin.language
audience: tenant_admin
plans:
  - starter
  - pro
channels:
  - web
module: settings
capabilities:
  - tenant_settings
route: /admin/settings
help_targets:
  - admin.settings.language
title: Idioma
summary: Cambia el idioma que TrackPal usa para el espacio de trabajo de tu negocio.
search_tags:
  - idioma
  - locale
  - español
  - inglés
synonyms:
  - lenguaje
  - traducción
order: 20
safe_navigation:
  route: /admin/settings
  settings_category: locale
related_topics:
  - tenant-admin.dashboard
  - tenant-admin.profile
  - tenant-admin.password
tour:
  release_id: tenant-admin-tracer-1
  order: 2
  target: admin.settings.language
  conditional: false
---

# Idioma

El Idioma controla la interfaz de TrackPal y el contenido de Ayuda privada para el espacio de trabajo de tu negocio activo.

## Canal, requisitos y acciones

- **Canal:** Web. Las respuestas de WhatsApp siguen el idioma activo, pero el cambio se hace aquí.
- **Requisitos:** Inicia sesión como Tenant Admin y abre Configuración. La categoría Idioma está disponible en Starter y Pro.
- **Acciones:** Elige Idioma, selecciona el idioma disponible y guarda el cambio. La página vuelve a cargar el catálogo después de guardar correctamente.

## Resultados y estados

La navegación, las etiquetas de Configuración y los temas de Ayuda usan el idioma seleccionado después de actualizarlo. Mientras guarda, el control está ocupado. La selección actual permanece visible al cargar la página. Si el idioma no puede cargarse o guardarse, el idioma anterior continúa activo y aparece un error.

## Límites, consecuencias y recuperación

El idioma es una configuración del Tenant, por lo que aplica al negocio y no solo a una pestaña o a un administrador. No traduce mensajes de proveedores externos ni cambia credenciales, suscripciones o la vinculación de WhatsApp. Si la selección no persiste, recarga la página, confirma que la solicitud pueda llegar a TrackPal e intenta de nuevo. No borres una sesión activa ni cambies credenciales del buzón para recuperar un error de idioma.

## Límite de soporte

Soporte puede ayudarte si el selector o el catálogo siguen sin estar disponibles después de reintentar. Incluye el idioma seleccionado y el error visible, pero nunca una contraseña, código de vinculación, token o secreto del buzón.
