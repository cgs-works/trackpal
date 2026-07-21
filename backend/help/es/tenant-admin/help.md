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
summary: Encuentra el manual privado y repite el recorrido de orientación opcional.
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
    title: Ayuda y repetición
    content: |
      # Ayuda y repetición

      Ayuda contiene los temas del manual autorizados para tu plan Starter, incluidos WhatsApp, las plataformas habilitadas, el buzón central y el control de acceso. Usa el buscador para encontrar un tema sin perder tus datos actuales.

      Puedes repetir esta orientación desde Ayuda cuando quieras. Los enlaces del manual solo abren pantallas seguras; nunca envían formularios, muestran credenciales ni realizan acciones del producto.
---

# Ayuda

La Ayuda privada es el lugar para leer orientación que coincide con tu rol Tenant Admin, tu plan actual y tu idioma.

## Encuentra un tema

Busca una acción, estado, error o requisito. La Ayuda Starter incluye Dashboard, Configuración, WhatsApp, plataformas de códigos habilitadas, buzón central, control de acceso, perfil, contraseña y la guía de búsqueda de códigos. Clientes, Catálogo, Suscripciones, recordatorios, zona horaria y administración de API pública, que son funciones Pro, no se muestran a usuarios Starter.

## Repite la orientación

La orientación Starter opcional explica el mapa operativo en aproximadamente de 2 a 3 minutos. Elige Repetir recorrido de orientación cuando quieras verlo otra vez. Cerrar el recorrido requiere confirmación antes de guardar el estado omitido.

La navegación de Ayuda es de solo lectura. Sus enlaces abren módulos o categorías de Configuración autorizados sin guardar formularios, cambiar estados, conectar servicios, mostrar secretos ni iniciar una búsqueda.
