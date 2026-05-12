# n8n WhatsApp Workflow

## Overview

Single n8n workflow que orquesta la interacción del Master con Trackpal vía WhatsApp.

- **Instancia**: `https://rs-n8n.wilfredocamacho.dev`
- **Workflow**: `Trackpal WhatsApp Bot` (ID: `vtqUvdkNnTNcKnwj`)
- **Webhook**: `POST /webhook/trackpal-whatsapp-bot`
- **Workflow export**: `n8n/trackpal-whatsapp-bot.workflow.json`

## Node flow

```
WhatsApp → Evolution API → Webhook (1)
                             ↓
                       Parse input (2)
                        → extrae phone, message, instance
                             ↓
                       Identify user (3)
                        → GET Trackpal API /identify?phone=
                        → Header: X-API-Key
                             ↓
                       Merge identity (4)
                        → combina datos + identidad
                             ↓
                       Route by role (5) [IF]
                        ├─ true (master) → Menu router (7)
                        └─ false → Access denied (6)
                                      ↓
                               Evolution API Send (8)

Menu router (7) → Is list action? (9) [IF]
                  ├─ true → List tenants API (10)
                  │           → Format list (11)
                  │             ↓
                  │       Evolution API Send (8)
                  └─ false → Evolution API Send (8)
```

## Session management

Multi-step operations (create, view, edit, deactivate, reactivate, delete) use session state carried in `session` property:

```json
{
  "phone": "521234567890",
  "step": "awaiting_full_name",
  "temp_data": "{}"
}
```

### Steps

| Step | Description |
|---|---|
| `awaiting_full_name` | Crear tenant: esperando nombre completo |
| `awaiting_email` | Crear tenant: esperando email |
| `awaiting_username` | Crear tenant: esperando username |
| `awaiting_password_choice` | Crear tenant: auto o manual? |
| `awaiting_password_manual` | Crear tenant: contraseña manual |
| `awaiting_tenant_id_view` | Ver tenant: esperando ID |
| `awaiting_tenant_id_edit` | Editar tenant: esperando ID |
| `awaiting_edit_fields` | Editar tenant: esperando campos JSON |
| `awaiting_tenant_id_deactivate` | Desactivar: esperando ID |
| `awaiting_tenant_id_reactivate` | Reactivar: esperando ID |
| `awaiting_tenant_id_delete` | Eliminar: esperando ID |

## Configuration

Antes de activar el workflow, reemplazar los placeholders en el export JSON:

| Placeholder | Descripción |
|---|---|
| `YOUR_TRACKPAL_API_URL` | URL base de la API (ej: `https://xxxx.ngrok-free.app/api/v1`) |
| `YOUR_TRACKPAL_API_KEY` | API key configurada en `N8N_API_KEY` del backend |
| `YOUR_EVOLUTION_API_URL` | URL de Evolution API (ej: `https://evo.midominio.com`) |
| `YOUR_EVOLUTION_API_KEY` | API key de Evolution API |

## Data table

- **Nombre**: `wa_sessions`
- **Columnas**: `phone` (string), `step` (string), `temp_data` (string), `created_at` (date), `updated_at` (date)
- **ID**: `tOsSN3fuGDtB0Svf`

## Development

El webhook de Evolution API debe configurarse para POSTear a:
```
https://rs-n8n.wilfredocamacho.dev/webhook/trackpal-whatsapp-bot
```

La URL de Trackpal API actualmente apunta a un túnel ngrok que cambia al reiniciar. Al desplegar la API con URL fija, actualizar en los nodos "Identify user" y "List tenants API".
