---
id: tenant-admin.access-control
audience: tenant_admin
plans:
  - starter
  - pro
channels:
  - web
  - whatsapp
module: settings
capabilities:
  - tenant_access_control
route: /admin/settings
help_targets:
  - admin.settings.access-control
title: Control de acceso de WhatsApp
summary: Revisa, busca, bloquea y desbloquea identidades de WhatsApp del Tenant.
search_tags:
  - control de acceso
  - teléfono bloqueado
  - identidad bloqueada
  - desbloquear
  - bloqueo de WhatsApp
synonyms:
  - bloqueo del bot
  - contactos bloqueados
  - denegar acceso
order: 80
safe_navigation:
  route: /admin/settings
  settings_category: access-control
related_topics:
  - tenant-admin.whatsapp
  - tenant-admin.activate-access-code-lookup
  - tenant-admin.profile
---

# Control de acceso de WhatsApp

El Control de acceso de WhatsApp es la lista de identidades que un Tenant Admin impide usar el bot de WhatsApp del Tenant. Protege la consola y el flujo de códigos de acceso; es diferente del estado de la cuenta de un Cliente en el portal.

## Canal, requisitos y acciones

- **Canales:** Web para ver la lista completa y buscar teléfonos; WhatsApp para el menú de Control de acceso del Tenant Admin.
- **Requisitos:** Ser Tenant Admin. Debe existir un teléfono o una identidad de WhatsApp que quieras bloquear. El bloqueo está disponible en Starter y Pro.
- **Acciones:** En Web, abre Configuración, elige Control de acceso, busca por los dígitos del teléfono, bloquea un teléfono o desbloquea una entrada existente. En WhatsApp, Starter abre Control de acceso con `3` y Pro con `5`; elige `1` para listar identidades bloqueadas o `2` para bloquear un teléfono.

## Resultados y estados

- **Cargando:** TrackPal está obteniendo las identidades bloqueadas. Espera antes de concluir que la lista está vacía.
- **Vacío:** No hay identidades bloqueadas; Web muestra el estado vacío y WhatsApp puede mostrar una lista vacía.
- **Bloqueado:** La identidad no puede entrar al bot de WhatsApp, pedir códigos de acceso ni usar acciones de la consola.
- **Desbloqueado:** Al eliminar la entrada, la identidad puede volver a usar WhatsApp cuando cumple los demás requisitos.
- **Duplicado:** Intentar bloquear una identidad ya bloqueada conserva la entrada existente.
- **Sin resultados:** Una búsqueda por teléfono puede no encontrar un bloqueo; limpia la búsqueda o revisa los dígitos.
- **Error:** Un fallo al listar, bloquear o desbloquear conserva el estado actual. Reintenta y contacta a soporte si continúa.

## Acciones en Web y WhatsApp

La lista Web permite buscar teléfonos sin cambiar los bloqueos guardados. En WhatsApp, usa `9` para volver al menú principal y `0` para cancelar la acción actual. El bloqueo del bot afecta el acceso de la identidad a WhatsApp; no cierra la sesión del Cliente en el portal ni cambia el estado activo/inactivo de su cuenta.

## Límites, consecuencias y recuperación

Bloquear impide que la identidad entre a la consola de WhatsApp del Tenant, solicite códigos de acceso, vea el perfil por WhatsApp o consulte suscripciones por WhatsApp. No elimina al Cliente, desactiva su cuenta del portal ni elimina suscripciones. Desbloquea la identidad exacta desde Web o desde la lista de WhatsApp cuando deba recuperar el acceso. Si un teléfono aparece como LID de WhatsApp, usa la identidad que muestra TrackPal y pide ayuda a soporte en vez de adivinar un teléfono.

## Límite de soporte

Soporte puede ayudarte a identificar un bloqueo persistente o una identidad que no coincide. Comparte el teléfono o identidad visible y la hora aproximada; nunca envíes una contraseña, código de acceso, código de vinculación, imagen QR ni credencial del buzón.
