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
summary: Define la zona horaria del negocio para fechas de suscripciones, recordatorios y vencimientos.
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

      Configuración reúne idioma, zona horaria, Clave API pública, plataformas habilitadas, buzón central, control de acceso, perfil, contraseña y vinculación de WhatsApp. La automatización Pro usa la zona horaria del negocio y los ajustes de recordatorios.

      Este paso abre una categoría informativa segura. El recorrido nunca guarda ajustes, conecta servicios, muestra claves, cambia accesos ni abre una confirmación destructiva.
---

# Zona horaria del negocio

La zona horaria se aplica a toda la cuenta del negocio, no solo a un navegador. TrackPal la usa para interpretar las fechas locales de las suscripciones y programar recordatorios de vencimiento. Esta sección aparece cuando esas herramientas están incluidas en el plan actual.

## Elegir y guardar una zona horaria

Abre Configuración, elige Zona horaria, busca por región o ciudad, selecciona la opción que corresponde a la ubicación del negocio y guarda. El valor predeterminado es `UTC`, una referencia horaria universal, hasta que elijas la región local. Idioma y zona horaria son ajustes separados: cambiar uno no traduce el otro ni modifica los datos de suscripciones.

Guardar cambia la zona horaria que se usará en los cálculos futuros de toda la cuenta del negocio. Help solo abre la categoría Zona horaria; no selecciona, guarda ni convierte un valor silenciosamente. Si la lista está cargando, espera. Si guardar falla, la zona horaria anterior sigue vigente y el error visible se puede reintentar.

## Qué cambia la zona horaria

- Los días de aviso de recordatorios usan la fecha del calendario local del negocio.
- La hora del recordatorio se interpreta como hora local antes de que TrackPal prepare el mensaje.
- La limpieza de vencimientos usa el final del día local del negocio antes de pasar una suscripción activa a Expirada.
- La creación y reactivación de suscripciones en WhatsApp usan la zona horaria del negocio al preparar el inicio y la confirmación.
- El dashboard y la información operativa de vencimientos deben interpretarse con el mismo calendario local del negocio.

La zona horaria no crea recordatorios, renueva suscripciones, reactiva registros cancelados, cancela una suscripción, conecta WhatsApp ni revela credenciales. Usa Suscripciones para acciones manuales y Ajustes de recordatorios para activación y destinatarios.

## Estados, límites y recuperación

Elige siempre una opción de la lista y comprueba la región si el negocio cambia de ubicación. TrackPal sigue automáticamente las reglas horarias de la región seleccionada, incluidos los cambios de horario de verano. Una zona horaria incorrecta puede hacer que un día de aviso parezca temprano o tarde sin cambiar el instante de vencimiento guardado.

El ajuste se aplica al negocio activo. No cambia el reloj del dispositivo de un cliente ni las fechas que muestra el proveedor de correo; solo cambia cómo TrackPal evalúa las fechas de suscripciones y recordatorios para el negocio.

## Navegación segura y límite de soporte

El enlace de Help abre Ajustes en la categoría Zona horaria sin guardar ni abrir un diálogo de modificación. Soporte puede ayudar a verificar el identificador elegido y un error visible de programación o vencimiento. Comparte solo la región, el valor IANA y la hora aproximada; nunca compartas contraseñas, PIN, credenciales del buzón, tokens OAuth, códigos de acceso ni secretos de vinculación de WhatsApp.
