---
id: tenant-admin.activate-access-code-lookup
audience: tenant_admin
plans:
  - starter
  - pro
channels:
  - web
  - whatsapp
module: help
capabilities:
  - tenant_access_code_lookup
route: /admin/settings
help_targets:
  - admin.settings.code-services
title: Preparar la búsqueda de códigos
summary: Completa WhatsApp, plataformas y buzón en el orden correcto.
search_tags:
  - activar búsqueda de códigos
  - primera búsqueda de código
  - configuración de códigos de acceso
  - requisitos de búsqueda
  - recuperación de búsqueda de códigos
synonyms:
  - habilitar búsqueda de códigos
  - primer código de acceso
  - configurar búsqueda de códigos
order: 90
safe_navigation:
  route: /admin/settings
  settings_category: code-services
related_topics:
  - tenant-admin.code-services
  - tenant-admin.mailbox
  - tenant-admin.whatsapp
  - tenant-admin.access-control
tour:
  - release_id: tenant-admin-starter-1
    order: 5
    target: admin.settings.code-services
    conditional: false
    plans:
      - starter
    title: Prepara la búsqueda de códigos
    content: |
      # Prepara la búsqueda de códigos

      Elige al menos una plataforma y conecta el buzón central. Después abre **Buscar código de acceso** desde WhatsApp.

      Pulsa **Más información** si quieres ver la preparación completa.
---

# Preparar la búsqueda de códigos

La búsqueda estará lista cuando completes estos tres pasos:

1. **Vincula WhatsApp** desde Configuración y espera el estado **Conectado**.
2. **Elige al menos una plataforma** en Plataformas habilitadas.
3. **Conecta y prueba el buzón central** con Google, Microsoft o IMAP.

Después abre **Buscar código de acceso** en WhatsApp: opción `2` en **TrackPal Starter** u opción `7` en **TrackPal Pro**. Elige el servicio, escribe el correo de la suscripción y confirma.

## Entender el resultado

- **Pendiente:** TrackPal sigue revisando el buzón; espera antes de repetir.
- **Encontrado:** usa pronto el código o enlace recibido.
- **No encontrado:** solicita un código nuevo al servicio y vuelve a intentarlo.
- **Duplicado:** espera el tiempo indicado antes de otra búsqueda.
- **Error o timeout:** comprueba primero el buzón y la plataforma.

Dentro del menú usa `8` para avanzar cuando aparezca, `9` para regresar y `0` para cancelar. Si el problema continúa, comparte el servicio, el estado visible y la hora aproximada, nunca el código ni la contraseña del correo.
