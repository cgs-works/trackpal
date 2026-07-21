---
id: tenant-admin.public-api
audience: tenant_admin
plans:
  - pro
channels:
  - web
module: settings
capabilities:
  - tenant_catalog
  - tenant_public_api
  - tenant_settings
route: /admin/settings
help_targets:
  - admin.settings.public-api
title: Publicar el catálogo mediante API pública
summary: Prepara una integración de navegador de solo lectura y entrega instrucciones seguras a tu desarrollador.
search_tags:
  - API pública
  - Clave API
  - sitios autorizados
  - catálogo en navegador
  - entrega al desarrollador
  - catálogo de solo lectura
  - Cloudflare
synonyms:
  - catálogo para sitio web
  - catálogo externo
  - integración frontend
  - paquete para desarrollador
order: 155
safe_navigation:
  route: /admin/settings
  settings_category: public-api
safe_links:
  - route: /admin/catalog
    settings_category: null
related_topics:
  - tenant-admin.catalog
  - tenant-admin.first-pro-client
tour:
  - release_id: tenant-admin-pro-upgrade-1
    order: 5
    target: admin.settings.public-api
    conditional: false
    plans:
      - pro
    title: API pública y ajustes Pro
    content: |
      # Nuevas herramientas de publicación Pro

      Tu upgrade agrega la API pública de Catálogo de solo lectura. Junto con los nuevos controles Pro de zona horaria y recordatorios, completa las capacidades Pro que no estaban disponibles en tu plan anterior.

      El recorrido es seguro e informativo: nunca crea, muestra, regenera, revoca ni copia una clave y nunca guarda un ajuste.
---

# Publicar el catálogo mediante API pública

La API pública de catálogo permite mostrar los servicios y planes de tu negocio en un sitio web cuando esta función está incluida en el plan actual. Es **de solo lectura**: los visitantes pueden ver nombres de servicios y planes, pero no pueden cambiar datos de TrackPal ni ver credenciales. Este tema explica la configuración sin crear, mostrar, reemplazar ni eliminar una clave.

## Prepara el Catálogo y los sitios autorizados

Primero prepara el Catálogo. Crea los servicios y planes que el sitio web debe mostrar y confirma sus nombres y orden en Catálogo. El endpoint público lee el Catálogo actual, por lo que los cambios posteriores aparecen sin copiar registros al sitio web.

Un sitio autorizado es el origen exacto del navegador donde funcionará el catálogo. Registra el esquema completo `http://` o `https://`, el host y el puerto opcional, por ejemplo `https://tienda.example.com` o `http://localhost:5173`. No agregues una ruta, query, fragmento, wildcard ni una URL de servidor. El `Origin` del navegador debe coincidir exactamente; el uso servidor a servidor está fuera de esta versión.

## Crea la clave y conecta el sitio

Abre Configuración, elige Clave API, agrega al menos un sitio autorizado y crea la clave. Mantén la clave fuera del control de versiones, capturas, chats públicos y logs del frontend. El paquete para desarrollador de este panel contiene el marcador `YOUR_PUBLIC_API_KEY` y ejemplos mantenidos para HTML + JavaScript, React, Vue, Svelte, Angular y Alpine.js. Nunca inserta la clave real de este negocio. Envía el paquete por separado y comparte la clave real mediante un canal seguro.

La integración del navegador hace una solicitud `GET` a `/api/v1/public/catalog?api_key=YOUR_PUBLIC_API_KEY`. El navegador envía `Origin` automáticamente. TrackPal devuelve el catálogo de solo lectura solo cuando la clave y el origen exacto son válidos. La ausencia de Origin, una clave desconocida, un origen distinto o una degradación a Starter producen una respuesta prohibida.

Los ejemplos del paquete son referencias, no un manual REST completo. Elige el ejemplo que corresponda a la tecnología que ya usa el sitio. Los enlaces de Ayuda solo abren esta categoría de Configuración o Catálogo; nunca guardan el formulario ni llaman una operación de API.

## Ciclo de vida y consecuencias

Regenerar la clave reemplaza la anterior y conserva los sitios autorizados. Cada integración que use el valor anterior debe actualizarse, y el valor anterior deja de autorizar solicitudes. Revocar o eliminar la clave borra la configuración pública y desactiva el catálogo en los sitios conectados. Es irreversible desde el punto de vista de la integración; para volver a publicar tendrás que crear y compartir otra clave por separado.

Cambiar un sitio autorizado afecta inmediatamente la autorización del navegador. Quitar un sitio no borra datos del Catálogo, pero ese sitio recibirá una respuesta prohibida hasta que su origen exacto vuelva a registrarse. El borrado del Catálogo es una acción destructiva separada con su propia vista previa de impacto.

## Estados, protección y recuperación

La ausencia de clave significa que todavía no se creó la integración pública. Un sitio vacío o inválido se rechaza antes de crear la clave. Una respuesta prohibida normalmente significa que no coinciden la clave, el `Origin`, el plan o el sitio registrado; verifica el esquema, host y puerto exactos sin agregar una ruta. Si falla una solicitud al Catálogo, confirma que el navegador está en un sitio autorizado y revisa el error visible antes de reintentar.

Antes de exponerlo ampliamente en producción, protege `GET /api/v1/public/catalog` con una regla de rate limit o WAF de Cloudflare para todo el tráfico público. Cloudflare es el límite esperado contra abuso para esta ruta pública; no agregues como solución un rate limiter de aplicación, Redis o memoria.

Este tema permanece oculto cuando el plan actual no incluye la publicación del catálogo en un sitio web. Una degradación pausa el acceso público, pero conserva la configuración de la clave para una futura reactivación Pro. Contacta a soporte con el endpoint público, el origen exacto, el estado de respuesta y el error visible no secreto; nunca envíes la Clave API.
