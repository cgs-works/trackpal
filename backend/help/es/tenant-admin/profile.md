---
id: tenant-admin.profile
audience: tenant_admin
plans:
  - starter
  - pro
channels:
  - web
module: settings
capabilities:
  - tenant_settings
route: /admin/settings
help_targets:
  - admin.settings.profile
title: Perfil
summary: Actualiza la identidad y la información de contacto del negocio que usa TrackPal.
search_tags:
  - perfil
  - nombre
  - email
  - teléfono
  - teléfono de WhatsApp
synonyms:
  - datos de cuenta
  - información del negocio
order: 40
safe_navigation:
  route: /admin/settings
  settings_category: profile
related_topics:
  - tenant-admin.dashboard
  - tenant-admin.language
  - tenant-admin.whatsapp
tour:
  - release_id: tenant-admin-starter-1
    order: 3
    target: admin.settings.profile
    conditional: false
    plans:
      - starter
    title: Configuración de la cuenta
    content: |
      # Configuración de la cuenta

      Configuración reúne el mapa de tu cuenta. Idioma cambia el idioma del espacio de trabajo, Perfil contiene la identidad y el teléfono del negocio que se usa para preparar WhatsApp, y Contraseña cambia solo la contraseña del administrador que inició sesión.

      Este paso abre el panel seguro de Perfil como un objetivo real. El recorrido nunca guarda un formulario, cambia una contraseña ni muestra valores sensibles.
---

# Perfil

Perfil guarda la identidad y los datos de contacto del negocio que los administradores usan para configurar TrackPal.

## Canal, requisitos y acciones

- **Canal:** Web. Editar el perfil no está disponible como acción de WhatsApp.
- **Requisitos:** Inicia sesión como administrador y abre Configuración, luego Perfil.
- **Acciones:** Revisa los campos de nombre del negocio, email y teléfono; cambia los valores permitidos y selecciona Guardar perfil.

## Resultados y estados

Después de guardar correctamente aparece una confirmación y los valores actualizados permanecen en el formulario. Cargando significa que TrackPal está obteniendo el perfil actual. Los errores de validación indican un valor que debes corregir. Un error al guardar conserva el perfil anterior en el servidor y mantiene disponible el formulario local para recuperarlo.

## Límites, consecuencias y recuperación

Los valores del perfil identifican al negocio y pueden proporcionar el requisito del teléfono de WhatsApp. Guardar no vincula ni desconecta WhatsApp, no envía mensajes, no cambia la contraseña ni modifica datos de clientes. Usa un número que pertenezca al negocio y siga el formato mostrado por el formulario. Si guardar falla, corrige los mensajes de validación y reintenta sin actualizar la página; actualizarla puede descartar cambios locales sin guardar.

## Límite de soporte

Soporte puede ayudarte con la validación o con un guardado que falle repetidamente. Comparte solo el nombre del campo y el mensaje de error. No compartas contraseñas, códigos de vinculación de WhatsApp, claves API ni credenciales del buzón.
