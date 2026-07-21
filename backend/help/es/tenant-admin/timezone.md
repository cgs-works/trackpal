---
id: tenant-admin.timezone
audience: tenant_admin
plans:
  - pro
channels:
  - web
module: settings
capabilities:
  - tenant_settings
  - tenant_subscriptions
route: /admin/settings
help_targets:
  - admin.settings.timezone
title: Zona horaria del negocio
summary: Alinea vencimientos y recordatorios con la hora local de tu negocio.
search_tags:
  - zona horaria
  - timezone
  - zona IANA
  - hora local
  - fecha local
  - horario de verano
synonyms:
  - zona horaria del negocio
  - hora regional
  - ajustes del reloj
order: 150
safe_navigation:
  route: /admin/settings
  settings_category: timezone
related_topics:
  - tenant-admin.reminders
  - tenant-admin.subscriptions
  - tenant-admin.subscription-expirations
tour:
  - release_id: tenant-admin-pro-1
    order: 6
    target: admin.settings.timezone
    conditional: false
    plans:
      - pro
    title: Configuración de TrackPal Pro
    content: |
      # Ajusta TrackPal a tu negocio

      Configura la zona horaria, los recordatorios, WhatsApp, el buzón central y las demás herramientas que mantienen tu operación conectada.
---

# Zona horaria del negocio

TrackPal usa esta zona para interpretar las fechas de suscripciones, la hora de los recordatorios y el cierre de cada día.

Abre **Configuración > Zona horaria**, busca tu región o ciudad, selecciónala y guarda. Hasta que elijas una, TrackPal usa `UTC` como referencia.

El ajuste se aplica a todo el negocio y sigue automáticamente los cambios horarios de la región. Si eliges una zona incorrecta, un aviso puede parecer temprano o tarde aunque la fecha guardada no haya cambiado.

Si no puedes guardar, la zona anterior seguirá activa. Comprueba la región seleccionada y vuelve a intentarlo.
