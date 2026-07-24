---
id: tenant-admin.delete-account
audience: tenant_admin
plans:
  - starter
  - pro
channels:
  - web
module: data
capabilities:
  - tenant_delete_account
route: /admin/settings
help_targets:
  - admin.settings.my-account
  - admin.settings.data-tab
  - admin.settings.danger-zone
title: Eliminación de cuenta
summary: Elimina permanentemente tu cuenta de TrackPal y todos los datos asociados. Esta acción es inmediata e irreversible.
search_tags:
  - eliminar
  - borrar
  - cancelar
  - cerrar cuenta
  - salir
synonyms:
  - eliminar cuenta
  - cerrar cuenta
  - cancelar cuenta
  - borrar cuenta
  - salir de la plataforma
order: 5
safe_navigation:
  route: /admin/settings
  settings_category: data
safe_links:
  - route: /admin/settings
    settings_category: data
related_topics:
  - tenant-admin.data-export
  - tenant-admin.dashboard
  - tenant-admin.help
---

# Eliminación de cuenta

Puedes eliminar permanentemente tu cuenta de TrackPal y todos los datos asociados. Esta acción es inmediata e irreversible — no hay período de gracia ni ventana de recuperación.

## Qué se elimina

- Tu cuenta y credenciales de inicio de sesión
- Todas las cuentas de clientes y su acceso
- Tu catálogo de servicios y todos los planes
- Todos los registros de suscripciones y su historial
- La configuración del correo y las credenciales almacenadas
- La lista de teléfonos bloqueados
- Las preferencias guardadas (idioma, zona horaria)
- Cualquier exportación de datos pendiente o guardada
- Tu instancia de WhatsApp Evolution

## Qué NO se elimina con esta acción

- **Concesiones OAuth del proveedor**: Los permisos de Google y Microsoft no se revocan. Puedes gestionarlos desde la configuración de seguridad de tu proveedor.
- **Respaldos de infraestructura**: Las copias de seguridad operativas y los registros siguen sus políticas de retención estándar. Se usan solo para recuperación de desastres y no son accesibles después de la eliminación.
- **Sesiones efímeras**: Cualquier sesión activa de WhatsApp o Web expira en minutos.

## Antes de eliminar

Considera descargar una [Exportación de datos](data-export.md) primero. La exportación te da una copia portátil de tu perfil de cuenta, clientes, catálogo y registros de suscripciones.

La eliminación está disponible incluso sin una exportación — el paso de exportación es opcional.

## Cómo eliminar tu cuenta

1. Ve a **Configuración > Mi cuenta > Datos**.
2. Desplázate hasta la **Zona de peligro** al final.
3. Haz clic en **Eliminar cuenta permanentemente**.
4. Ingresa tu contraseña actual.
5. Escribe **ELIMINAR** para confirmar.
6. Haz clic en **Eliminar permanentemente**.

Después de la eliminación exitosa, se te cerrará la sesión y serás redirigido a la página de inicio de sesión. No podrás iniciar sesión nuevamente con esta cuenta.

## Qué sucede durante la eliminación

1. Cualquier exportación en curso se cancela.
2. Los archivos de exportación almacenados se eliminan permanentemente.
3. Tu instancia de WhatsApp Evolution se elimina.
4. Tu cuenta y todos los datos se eliminan de la base de datos activa.
5. Tu sesión web se limpia.

Si la limpieza externa (eliminación de exportación, eliminación de Evolution) falla, la cuenta se conserva y puedes intentarlo de nuevo. Esto evita una eliminación parcial.

## Relacionados

- [Exportación de datos](data-export.md) — Descarga tus datos antes de eliminar
