---
id: client.whatsapp
audience: client
plans:
  - pro
channels:
  - whatsapp
module: help
capabilities:
  - client_whatsapp
route: /client/dashboard
help_targets: []
title: Consola de Cliente en WhatsApp
summary: Usa las acciones disponibles de WhatsApp sin confundirlas con los cambios de cuenta exclusivos de Web.
search_tags:
  - WhatsApp
  - perfil
  - suscripciones
  - código de acceso
  - salir
synonyms:
  - menú de chat
  - menú del bot
order: 50
safe_navigation:
  route: /client/dashboard
  settings_category: null
related_topics:
  - client.dashboard
  - client.profile
  - client.subscriptions
  - client.password
---

# Consola de Cliente en WhatsApp

La consola de Cliente en WhatsApp es un canal separado y limitado para consultar información y solicitar una búsqueda de código de acceso mediante el flujo configurado por el proveedor.

## Canal, requisitos y acciones

- **Canal:** WhatsApp. Tu proveedor debe tener una configuración Pro activa y un flujo de WhatsApp que reconozca tu cuenta de Cliente.
- **Requisitos:** Usa el teléfono asociado a la cuenta de Cliente y sigue el menú enviado por el bot. El proveedor debe tener configurados el correo central y la plataforma habilitada necesarios para buscar códigos de acceso.
- **Acciones:** Consulta tu perfil, consulta suscripciones activas, busca un código de acceso cuando la opción esté disponible y sal de la consola. Sigue las etiquetas actuales del menú en lugar de adivinar números.

## Límite exclusivo de Web

Los cambios de contraseña son exclusivos de Web. Abre la página Perfil web para esa acción. WhatsApp no puede editar tu nombre, teléfono, proveedor, estado, suscripciones ni credenciales de servicios.

## Resultados, navegación y recuperación

Una solicitud correcta devuelve el perfil, la suscripción o el resultado de búsqueda permitido. Una configuración faltante, una suscripción no disponible, una entrada inválida o un tiempo de espera muestran un mensaje recuperable; sigue la indicación o inicia una sesión nueva. Usa la opción de salida del menú al terminar. No envíes contraseñas, credenciales, códigos de vinculación ni comandos privados arbitrarios al bot.

## Límite de soporte

El proveedor controla el acceso de Cliente a WhatsApp y la configuración de búsqueda del correo. Comparte con soporte solo el error visible y la hora aproximada; nunca envíes una contraseña, código de acceso, credencial de suscripción ni contenido privado del mensaje.
