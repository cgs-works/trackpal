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
title: Zona horaria del Tenant
summary: Define la zona horaria IANA usada para fechas locales, recordatorios y automatización de vencimientos.
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
    title: Configuración Pro y preparación segura
    content: |
      # Configuración conecta las operaciones Pro

      Configuración reúne idioma, zona horaria, Clave API pública, plataformas habilitadas, buzón central, control de acceso, perfil, contraseña y vinculación de WhatsApp. La automatización Pro usa la zona horaria del Tenant y los ajustes de recordatorios.

      Este paso abre una categoría informativa segura. El recorrido nunca guarda ajustes, conecta servicios, muestra claves, cambia accesos ni abre una confirmación destructiva.
---

# Zona horaria del Tenant

La zona horaria del Tenant es un ajuste del negocio, no una preferencia exclusiva del navegador. TrackPal usa la zona IANA elegida para interpretar fechas locales de suscripciones y programar recordatorios de vencimiento. Está disponible para Tenant Admin Pro; los Tenant Admin Starter no pueden ver, recuperar ni buscar este topic. El Master Support Context puede revisar ajustes Pro conservados sin cambiar el plan del Tenant.

## Elegir y guardar una zona horaria

Abre Ajustes, elige Zona horaria, busca en el selector por región o identificador, selecciona el valor IANA correspondiente y guarda. El valor predeterminado es `UTC`. El selector muestra una etiqueta legible y su identificador para confirmar la ubicación del negocio antes de guardar. Idioma y zona horaria son ajustes separados: cambiar uno no traduce el otro ni modifica los datos de suscripciones.

Guardar cambia el valor global del Tenant usado por los cálculos futuros. Help solo abre la categoría Zona horaria; no selecciona, guarda ni convierte un valor silenciosamente. Si la lista está cargando, espera. Si guardar falla, la zona horaria anterior sigue vigente y el error visible se puede reintentar.

## Qué cambia la zona horaria

- Los días de aviso de recordatorios usan la fecha del calendario local del Tenant.
- La hora del recordatorio se interpreta como hora local y el backend la comprueba antes de crear un recordatorio pendiente.
- La limpieza de vencimientos usa el final del día local del Tenant antes de pasar una suscripción activa a Expirada.
- La creación y reactivación de suscripciones en WhatsApp usan la zona horaria del Tenant al preparar el inicio y la confirmación.
- El dashboard y la información operativa de vencimientos deben interpretarse con el mismo calendario local del Tenant.

La zona horaria no crea recordatorios, renueva suscripciones, reactiva registros cancelados, cancela una suscripción, conecta WhatsApp ni revela credenciales. Usa Suscripciones para acciones manuales y Ajustes de recordatorios para activación y destinatarios.

## Estados, límites y recuperación

Los servicios backend manejan defensivamente un valor ausente o inválido, pero se deben preferir los identificadores IANA válidos del selector. Comprueba la región después de cambios de horario de verano o cuando el negocio se mude. Una zona horaria incorrecta puede hacer que un día de aviso parezca temprano o tarde sin cambiar el instante de vencimiento guardado.

El ajuste aplica al Tenant activo y debe confirmarse después de cambiar de Tenant en soporte. No cambia el reloj personal del Cliente, las marcas de tiempo del proveedor de correo ni los instantes absolutos `starts_at` y `expires_at` guardados. Cambia cómo TrackPal evalúa esos instantes respecto a la fecha local del Tenant.

## Navegación segura y límite de soporte

El enlace de Help abre Ajustes en la categoría Zona horaria sin guardar ni abrir un diálogo de modificación. Soporte puede ayudar a verificar el identificador elegido y un error visible de programación o vencimiento. Comparte solo la región, el valor IANA y la hora aproximada; nunca compartas contraseñas, PIN, credenciales del buzón, tokens OAuth, códigos de acceso ni secretos de vinculación de WhatsApp.
