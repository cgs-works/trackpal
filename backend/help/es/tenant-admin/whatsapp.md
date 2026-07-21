---
id: tenant-admin.whatsapp
audience: tenant_admin
plans:
  - starter
  - pro
channels:
  - web
  - whatsapp
module: settings
capabilities:
  - tenant_whatsapp
route: /admin/settings
help_targets:
  - admin.settings.whatsapp
title: WhatsApp
summary: Vincula el teléfono de tu negocio y usa TrackPal desde el chat.
search_tags:
  - WhatsApp
  - código de vinculación
  - código QR
  - dispositivos vinculados
  - desconectar
synonyms:
  - conexión de WhatsApp
  - vincular teléfono
  - bot
order: 30
safe_navigation:
  route: /admin/settings
  settings_category: whatsapp-link
related_topics:
  - tenant-admin.dashboard
  - tenant-admin.profile
  - tenant-admin.language
tour:
  - release_id: tenant-admin-starter-1
    order: 4
    target: admin.settings.whatsapp
    conditional: false
    plans:
      - starter
    title: Conecta WhatsApp
    content: |
      # Conecta WhatsApp

      Vincula el teléfono del negocio para usar el menú privado de TrackPal Starter. Cuando veas **Conectado**, podrás continuar con la búsqueda de códigos y el Control de acceso.
---

# WhatsApp

Vincula el teléfono de tu negocio para administrar TrackPal desde un menú privado y enviar avisos.

## Conectar el teléfono

En **Configuración > Perfil**, confirma el número del negocio. Luego abre **WhatsApp**, elige código de vinculación o código QR y completa el proceso desde **Dispositivos vinculados** en tu teléfono. Espera hasta ver **Conectado**.

Si el código vence, genera uno nuevo. Usa **Desconectar** solo cuando quieras terminar la vinculación.

## Menús disponibles

**TrackPal Starter** incluye Perfil, búsqueda de códigos, Control de acceso, Ayuda y Salir. **TrackPal Pro** también incluye Clientes, Catálogo y Suscripciones.

En el menú de **TrackPal Pro**: `1` Clientes, `2` Catálogo, `3` Mi perfil, `4` Suscripciones, `5` Control de acceso, `6` Ayuda y `7` Buscar código. Usa `0` para salir o cancelar; `8` y `9` aparecen cuando puedes avanzar o regresar.

## Menú privado para un cliente

Escribe `menu` o `/menu` en tu chat privado de administración cuando estés atendiendo a un contacto. Desde allí puedes consultar o gestionar su cuenta y abrir sus suscripciones. Solo puedes mantener un menú de cliente activo a la vez; usa `0` para cerrarlo.

Si WhatsApp está conectado pero la búsqueda de códigos falla, revisa primero las plataformas habilitadas y el buzón central. No compartas códigos QR, códigos de vinculación ni contraseñas con soporte.
