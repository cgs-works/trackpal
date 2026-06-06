# Spec 2 — Copy visible y terminología de producto

## Estado

Aprobado para PR separado, posterior al PR de TPL-7.

## Resumen

Este PR limpia el lenguaje visible del producto sin tocar internals. El objetivo es que el usuario final no vea términos técnicos como “Tenant”, que el copy español tenga acentos y puntuación correcta, y que los textos frontend en español no tengan mojibake.

Este trabajo debe ejecutarse separado del PR funcional de TPL-7 para facilitar review: primero se corrige el bug del flujo, luego se normaliza copy/terminología.

## Objetivos

1. Eliminar “Tenant/tenant” de todo copy visible al usuario.
2. Mantener `tenant` en código, rutas, modelos, variables, nombres de archivos, nombres de componentes y keys i18n.
3. Corregir acentos, puntuación y capitalización natural en `catalogs_es_wa.py`.
4. Normalizar tono en español a “tú/informal profesional”.
5. Corregir mojibake en `catalogs_es_frontend.py`.
6. Aplicar terminología de producto consistente en ES y EN.
7. Actualizar tests que dependan de copy exacto usando fragmentos semánticos mínimos.

## No objetivos

Este PR no debe incluir:

- Cambios funcionales en flujos conversacionales.
- Cambios al comportamiento de TPL-7.
- Renombrado de modelos `Tenant`, rutas `/tenant`, componentes como `TenantDashboardView`, variables, stores o nombres de keys.
- Barrido global de docs técnicas para reemplazar “tenant”.
- Cambios de arquitectura i18n.
- Cambios en n8n salvo que exista copy visible hardcoded que lo requiera explícitamente.

## Principio rector

“Tenant” es un término interno de arquitectura SaaS. No debe aparecer en copy visible para Master, admins o clientes.

Sí puede permanecer en:

- Código.
- Modelos.
- Rutas.
- Migraciones.
- Repositorios.
- Nombres de carpetas/archivos.
- Nombres de keys i18n.
- Documentación técnica.
- Comentarios técnicos internos.

No debe permanecer en:

- UI frontend.
- WhatsApp replies.
- Mensajes de error user-facing.
- Labels visibles.
- Botones visibles.
- Mensajes de ayuda visibles.

## Terminología aprobada

| Contexto | Español visible | Inglés visible |
|---|---|---|
| Cliente final | proveedor | provider |
| Admin | administración / empresa / cuenta de administración | admin / business / admin account |
| Master en soporte | empresa / panel Master | business / Master dashboard |
| Recordatorios | administración / cliente | admin / client |
| Código interno, keys, rutas | se mantiene `tenant` | se mantiene `tenant` |

## Decisiones específicas aprobadas

### Pantallas del cliente

Usar “proveedor/provider”.

Ejemplos:

```text
Tus suscripciones activas con este proveedor.
```

```text
Your active subscriptions with this provider.
```

Si existe nombre de empresa/proveedor, preferir el nombre específico:

```text
Tus suscripciones activas con *{provider_name}*.
```

### Master en modo soporte

Cuando el Master está gestionando una empresa específica en modo soporte, evitar “tenant”.

Texto recomendado:

```text
Estás gestionando esta empresa en modo soporte.
```

Botón aprobado:

```text
Volver al panel Master
```

Inglés:

```text
Back to Master dashboard
```

### Recordatorios

Para recipient modes, usar administración/admin, no empresa/business.

| Key interna | ES visible | EN visible |
|---|---|---|
| `frontend.subscriptions.recipient_mode_tenant_only` | Solo administración | Admin only |
| `frontend.subscriptions.recipient_mode_client_only` | Solo cliente | Client only |
| `frontend.subscriptions.recipient_mode_both` | Administración y cliente | Admin and client |

La key puede conservar `tenant` porque no es visible.

### Consola Master de WhatsApp

Usar “empresa” como término principal.

Ejemplo:

```text
🤖 *Trackpal Master Console*

1️⃣ Ver empresas
2️⃣ Crear empresa
3️⃣ Desactivar empresa
4️⃣ Eliminar empresa
5️⃣ Ayuda

0️⃣ Cerrar sesión

Responde con el número de la opción deseada.
```

Prompts:

```text
✏️ *Crear empresa*

Vamos a crear una nueva empresa.

¿Cuál es el *nombre completo* de la empresa?
```

Mensaje vacío:

```text
📭 No hay empresas registradas.
```

Los flows internos pueden seguir siendo `list_tenants`, `create_tenant`, `tenant_detail`, etc.

## Alcance de archivos

Archivos probables a revisar/tocar:

- `backend/app/core/i18n/catalogs_es_wa.py`
- `backend/app/core/i18n/catalogs_en_wa.py`
- `backend/app/core/i18n/catalogs_es_frontend.py`
- `backend/app/core/i18n/catalogs_en_frontend.py`
- `backend/app/services/whatsapp_console_service/messages.py`
- Archivos backend con mensajes user-facing hardcoded.
- Componentes Vue con strings visibles hardcoded.
- Tests que dependan de copy exacto.

Fuera de alcance salvo hallazgo específico:

- Modelos, repositorios, rutas, migraciones.
- Docs técnicas.
- Nombres de keys i18n.
- Nombres de componentes como `TenantDashboardView.vue`.

## Corrección de español en WhatsApp

En `catalogs_es_wa.py`:

- Corregir acentos.
- Agregar signos de apertura `¿` / `¡` donde correspondan.
- Mejorar puntuación.
- Mejorar capitalización natural.
- Normalizar tono a “tú/informal profesional”.
- Conservar significado funcional de cada mensaje.
- No cambiar opciones numéricas ni navegación fuera de cambios ya implementados en PR 1.

Ejemplos:

```text
Opcion invalida.
```

pasa a:

```text
❌ Opción inválida.
```

```text
Que campo desea editar?
```

pasa a:

```text
¿Qué campo deseas editar?
```

```text
Telefono registrado.
```

pasa a:

```text
Teléfono registrado.
```

```text
Creando suscripcion para *{client_name}*
```

pasa a:

```text
Creando suscripción para *{client_name}*.
```

## Corrección de mojibake frontend español

En `catalogs_es_frontend.py`, corregir textos rotos como:

```text
Iniciar sesiÃ³n
ContraseÃ±a
TelÃ©fono
SÃ­
Â¿EstÃ¡s seguro...?
```

A:

```text
Iniciar sesión
Contraseña
Teléfono
Sí
¿Estás seguro...?
```

También revisar otros casos de mojibake visibles.

## Eliminación de “Tenant/tenant” visible

### Frontend ES

Ejemplos esperados:

| Actual | Nuevo |
|---|---|
| Dashboard de tenant | Panel de administración |
| Salir de tenant | Volver al panel Master |
| Solo el tenant | Solo administración |
| Tenant y cliente | Administración y cliente |
| Tenant | Proveedor / Empresa / Administración según contexto |
| Tus suscripciones activas en este tenant. | Tus suscripciones activas con este proveedor. |
| Estás gestionando el catálogo de este tenant en modo soporte. | Estás gestionando esta empresa en modo soporte. |

### Frontend EN

| Current | New |
|---|---|
| Tenant Dashboard | Admin Dashboard |
| Exit tenant | Back to Master dashboard |
| Tenant only | Admin only |
| Tenant and client | Admin and client |
| Tenant | Provider / Business / Admin depending on context |
| Your active subscriptions in this tenant. | Your active subscriptions with this provider. |
| You are managing this tenant's catalog in support mode. | You are managing this business in support mode. |

## Tratamiento por actor

### Master

Usar:

- empresa
- cuenta
- panel Master
- modo soporte

Evitar:

- tenant
- cuenta tenant
- dashboard tenant

### Admin

Usar:

- administración
- cuenta de administración
- tu empresa
- consola de administración

Evitar:

- tenant
- menú tenant
- tenant console

### Cliente final

Usar:

- proveedor
- tu proveedor
- administrador del servicio, si no hay proveedor específico

Evitar:

- tenant
- empresa, cuando el cliente final necesita entender quién le presta servicio; preferir proveedor

### Recordatorios

Usar:

- administración
- cliente

No usar “empresa” para recipient modes porque el destinatario real es el admin/canal administrativo, no la entidad legal.

## Testing

### Regla aprobada

Los tests nuevos o actualizados no deben depender de textos largos completos cuando no sea necesario.

Preferir fragmentos semánticos mínimos:

```python
assert "Opción inválida" in reply
assert "Crear suscripción" in reply
assert "Desactivar cliente" in reply
```

Evitar snapshots o comparaciones línea por línea para copy largo.

### Tests a revisar

Revisar tests que busquen fragmentos sin acento o términos “tenant” visibles, especialmente:

- Tests de WhatsApp Master Console.
- Tests de Tenant/Admin Console.
- Tests de Client Context Shortcut.
- Tests frontend/store si validan labels visibles.
- Tests de i18n catalog completeness.

Actualizar asserts de copy exacto al nuevo texto visible.

## Documentación

No hacer barrido global de docs técnicas.

Solo actualizar documentación si:

- Se documenta explícitamente un texto visible al usuario que cambia.
- Hay docs de producto/soporte que usan “tenant” como término visible para usuarios.

Mantener “tenant” en docs técnicas de arquitectura multi-tenant, modelos, RLS, rutas, etc.

## Criterios de aceptación

- Ningún texto visible al usuario en ES/EN muestra “Tenant” o “tenant”, salvo que sea parte de un identificador técnico visible solo a desarrolladores.
- `catalogs_es_wa.py` tiene acentos, puntuación y tono natural en las cadenas visibles.
- `catalogs_es_frontend.py` no contiene mojibake visible como `Ã`, `Â¿`, `Â`, `Ã±`, etc.
- Master WhatsApp usa “empresa” en menús, ayuda y prompts visibles.
- Pantallas de cliente usan “proveedor/provider”.
- Recipient modes usan “administración/admin” y “cliente/client”.
- Botón de salida de modo soporte dice `Volver al panel Master` / `Back to Master dashboard`.
- No se renombraron modelos, rutas, keys i18n ni internals.
- Tests relevantes pasan.

## Búsquedas sugeridas de verificación

Después de implementar, buscar en archivos user-facing:

```bash
rg -n "Tenant|tenant" backend/app/core/i18n frontend/src backend/app/services
```

Luego clasificar resultados:

- Si es key, ruta, variable, clase, comentario técnico → puede quedarse.
- Si es valor visible o texto hardcoded visible → debe cambiar.

Buscar mojibake:

```bash
rg -n "Ã|Â|�" backend/app/core/i18n frontend/src
```

Buscar términos españoles sin acento comunes en catálogos visibles:

```bash
rg -n "Opcion|Telefono|contrasena|suscripcion|Operacion|Sesion|catalogo|informacion|numero|valida|invalida" backend/app/core/i18n/catalogs_es_*.py
```

Revisar manualmente para evitar falsos positivos en keys o texto intencional.

## Riesgos

- Cambio amplio de copy puede romper tests frágiles. Mitigar actualizando asserts a fragmentos semánticos mínimos.
- Reemplazo automático de “tenant” podría tocar internals por accidente. Mitigar con revisión manual y mantener frontera estricta.
- “Empresa” y “proveedor” no son intercambiables. Usar según actor.
- Mojibake puede requerir reemplazo cuidadoso para no dañar strings ya correctos.

## Plan de implementación sugerido

1. Revisar catálogos frontend ES/EN y reemplazar valores visibles con terminología aprobada.
2. Corregir mojibake en `catalogs_es_frontend.py`.
3. Revisar `catalogs_es_wa.py` completo: acentos, puntuación, tono informal profesional.
4. Revisar `catalogs_en_wa.py` y `catalogs_en_frontend.py` para eliminar “Tenant/tenant” visible.
5. Revisar hardcoded visible en `whatsapp_console_service/messages.py`, especialmente consola Master.
6. Buscar strings visibles hardcoded en Vue y backend services.
7. Actualizar tests afectados.
8. Ejecutar búsquedas de verificación.
9. Ejecutar test suite relevante.
