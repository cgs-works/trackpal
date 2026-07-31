---
id: tenant-admin.data-export
audience: tenant_admin
plans:
  - starter
  - pro
channels:
  - web
module: data
capabilities:
  - tenant_data_export
route: /admin/settings
help_targets:
  - admin.settings.my-account
  - admin.settings.data-tab
title: Exportación de datos
summary: Solicita y descarga una copia puntual de los datos de tu cuenta como un ZIP con archivos CSV y JSON.
search_tags:
  - exportar
  - descargar
  - respaldo
  - datos
  - descarga
  - exportación
synonyms:
  - descarga de datos
  - paquete de datos
  - descargar datos
  - copia de datos
order: 4
safe_navigation:
  route: /admin/settings
  settings_category: data
safe_links:
  - route: /admin/settings
    settings_category: data
related_topics:
  - tenant-admin.delete-account
  - tenant-admin.dashboard
  - tenant-admin.help
---

# Exportación de datos

Puedes descargar una copia puntual de los datos de tu cuenta de TrackPal. La exportación es un archivo ZIP que contiene hojas de cálculo CSV y un documento JSON con tu perfil de cuenta, clientes, catálogo de servicios, registros de suscripciones y lista de teléfonos bloqueados.

## Qué incluye

| Archivo | Contenido |
|---------|-----------|
| `account-profile.csv` | Nombre de tu cuenta, correo de contacto, teléfono WhatsApp, nombre de usuario, plan actual, idioma y zona horaria |
| `client-data.csv` | Nombre del cliente, nombre de usuario, teléfono, estado de la cuenta, fechas de registro y última actualización |
| `service-catalog.csv` | Nombre del servicio, fechas de creación y actualización, nombre del plan y fechas del plan. Los servicios sin planes aparecen con campos de plan vacíos |
| `subscription-snapshot.csv` | Nombre y usuario del cliente, servicio, plan, correo y perfil de la cuenta de streaming, duración, fechas de inicio, vencimiento y cancelación, estado, marcas de tiempo |
| `blocked-phones.csv` | Teléfonos bloqueados y la fecha en que fueron bloqueados |
| `trackpal-data.json` | Los mismos datos en formato JSON con estructura legible por máquina |
| `README.txt` | Explicación de cada archivo y campo en tu idioma |

## Qué nunca se incluye

Por tu seguridad, la exportación excluye intencionalmente:

- Contraseñas (tu inicio de sesión, cuentas de clientes, suscripciones de streaming)
- PINs de perfil y cualquier indicación de que una contraseña o PIN está configurado
- Credenciales de inicio de sesión del correo o contraseñas de aplicación
- Tokens de Evolution API o Claves de API Pública
- Identificadores internos de base de datos o identificadores técnicos
- Identidades solo LID de WhatsApp del control de acceso
- Historial de cambios de suscripciones, registros de recordatorios o registros de entrega
- Trabajos de búsqueda en el correo o registros de entrega

Los valores de fecha y hora usan tu zona horaria. El nombre del archivo ZIP incluye el nombre de tu cuenta y la fecha de generación.

## Cómo solicitar una exportación

1. Ve a **Configuración > Mi cuenta > Datos**.
2. Ingresa tu contraseña actual cuando se te solicite.
3. El sistema crea tu exportación. El estado cambia de **Pendiente** a **Procesando** a **Listo**.
4. Cuando esté listo, haz clic en **Descargar ZIP** para guardar el archivo.

El estado se actualiza automáticamente mientras la pestaña Datos esté abierta.

## Límites

- **Tiempo de espera**: Una nueva exportación cada 24 horas. La cuenta regresiva muestra cuándo estará disponible la próxima.
- **Disponibilidad**: Una exportación lista permanece descargable durante 72 horas. Después de eso, se elimina automáticamente.
- **Reemplazo**: Solicitar una nueva exportación mientras una está lista mantiene la versión anterior disponible hasta que se genere la nueva.

## Cancelación

Puedes cancelar una exportación pendiente o en proceso. Si cancelas durante el procesamiento, cualquier carga parcial se descarta. La versión anterior lista (si existe) permanece disponible.

## Relacionados

- [Eliminación de cuenta](delete-account.md) — Elimina permanentemente tu cuenta
