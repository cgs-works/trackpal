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
title: Activar la búsqueda de códigos de acceso
summary: Conecta las dependencias en orden y ejecuta la primera búsqueda segura desde WhatsApp.
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
    title: Plataformas y buzón
    content: |
      # Completa la ruta de códigos de acceso

      Habilita al menos una plataforma disponible, conecta y prueba el buzón central y después usa el menú Starter de WhatsApp para solicitar una búsqueda de código. Son requisitos, no pasos de demostración: el recorrido no activa plataformas, conecta un buzón ni inicia una búsqueda.

      Las listas vacías y los estados desconectados son estados iniciales válidos. Elige **Más información** para consultar el orden de dependencias y la recuperación segura.
---

# Activar la búsqueda de códigos de acceso

Usa este camino cuando el negocio quiera encontrar un código de acceso de un servicio desde WhatsApp. Completa las dependencias en orden: la búsqueda solo está disponible después de vincular WhatsApp, habilitar una plataforma y preparar el buzón central.

## Cadena de dependencias

1. **Vincula WhatsApp:** En Configuración Web, configura el teléfono del negocio en Perfil, abre WhatsApp y vincula con un código de vinculación o código QR. Espera el estado Conectado. Un estado desconectado o un teléfono faltante debe recuperarse antes de continuar.
2. **Selecciona una plataforma:** En Configuración, abre Plataformas de códigos habilitadas, selecciona al menos un servicio activo globalmente y guarda. Si la lista está cargando, no disponible o devuelve un error, espera o reintenta antes de probar una búsqueda.
3. **Conecta el buzón:** En Configuración, abre Buzón central de consultas y conecta Google, Microsoft o IMAP personalizado. Usa Probar conexión y continúa solo cuando el estado sea Conectado. Una conexión pendiente, con error, revocada o con tiempo agotado necesita recuperación en esa categoría.
4. **Inicia desde el menú de WhatsApp:** Starter usa `2` para Buscar código de acceso. Pro usa `7`. Elige un servicio listado, escribe el email de la suscripción y revísalo antes de confirmar con `1`.
5. **Procesa el primer resultado:** La búsqueda queda pendiente mientras TrackPal revisa correos recientes del buzón. Un código o enlace encontrado se devuelve en la conversación de WhatsApp. Un resultado no encontrado, duplicado, con error o con tiempo agotado indica la recuperación correspondiente.

## Navegación y recuperación segura

El contrato compartido de navegación usa `0` para cancelar, mientras el mensaje actual etiqueta `8` y `9` para navegar páginas o regresar a la pantalla anterior. En la confirmación del email, `2` corrige el correo y `9` vuelve a la lista de servicios. Usa `0` en vez de enviar credenciales o abandonar una búsqueda a medias. Si la sesión expira, inicia el flujo otra vez desde el menú de tu plan.

## Estados y recuperación

- **Pendiente:** Espera el resultado en vez de iniciar búsquedas repetidas. Si no llega, aplica la recuperación de tiempo agotado y revisa el estado del buzón.
- **Encontrado:** Usa pronto el código porque los códigos de los servicios pueden expirar. Trata un enlace devuelto como información sensible y ábrelo solo si lo esperabas.
- **No encontrado:** Solicita un código nuevo en el servicio, espera el correo e inténtalo otra vez con el servicio y el email correctos.
- **Duplicado:** Espera el tiempo de enfriamiento mostrado y vuelve a intentar para obtener el código más reciente, en vez de repetir inmediatamente.
- **Error:** Comprueba que el buzón esté Conectado y que la plataforma seleccionada siga disponible; después reintenta.
- **Tiempo de espera agotado:** Revisa el proveedor y la conexión del buzón y comienza una búsqueda nueva. No desconectes una instancia sana de WhatsApp ni el buzón como primera respuesta.
- **Requisitos faltantes:** Vuelve a Configuración Web y completa la primera dependencia que falte. Las selecciones de plataformas y los datos del negocio se conservan al reparar una conexión.

## Acciones en Web y WhatsApp

El enlace de Ayuda en Web abre Configuración sin guardar formularios, conectar o desconectar servicios, bloquear o desbloquear identidades ni iniciar una búsqueda. El flujo de WhatsApp es el lugar donde se solicita la búsqueda; esta guía nunca pide pegar credenciales del buzón, contraseñas, tokens, códigos de vinculación o imágenes QR en el chat.

## Límite de soporte

Soporte puede rastrear un error, tiempo de espera o resultado inesperado persistente si recibe el servicio, estado del buzón, error visible y hora aproximada. Nunca envíes el código de acceso, contraseña del correo, token OAuth, código de vinculación ni imagen QR en una solicitud de soporte.
