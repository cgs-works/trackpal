# TPL-11 — Confirmación de email antes de buscar código de acceso

## Estado

Diseño aprobado en brainstorming. Este documento define el alcance para la implementación futura; no incluye cambios de código ejecutable.

## Contexto

TPL-11 solicita agregar un paso de confirmación después de que el usuario ingresa el email en el flujo de búsqueda de códigos de acceso, antes de crear o encolar cualquier búsqueda de mailbox.

El flujo afectado existe en dos caminos:

1. **Tenant Admin / Tenant Console**: `backend/app/services/whatsapp_tenant_console_service/codigo_flow.py`.
2. **Unauth / identidad no registrada**: `backend/app/api/v1/endpoints/integrations/console_handlers.py`.

Ambos caminos actualmente validan el email con reglas manuales simples y continúan inmediatamente hacia la búsqueda. La codebase ya tiene `email-validator` en `backend/pyproject.toml` y ya expone `app.core.input_validation.validate_email()` como validador central, por lo que la implementación debe reutilizar ese validador en lugar de importar `email_validator` directamente en los flujos.

## Objetivos

- Pedir confirmación del email antes de crear o marcar intención de crear un `MailLookupJob`.
- Aplicar el mismo comportamiento en Tenant Admin y unauth.
- Validar emails con `app.core.input_validation.validate_email(required=True)`.
- Guardar y procesar todos los emails como lowercase.
- Mantener i18n en español e inglés.
- Preservar los contratos existentes de retry/back/cancel después del resultado.
- Preservar el contrato de cierre Evolution en el flujo unauth al cancelar.

## No objetivos

- No refactorizar ni unificar los motores Tenant Admin y unauth.
- No cambiar el `mail_lookup_worker`.
- No modificar `backend/pyproject.toml`, porque `email-validator` ya está instalado.
- No agregar validación DNS/MX/deliverability.
- No cambiar el comportamiento de polling de n8n.

## Decisión aprobada

Se usará un cambio quirúrgico por flujo, sin crear un motor compartido nuevo.

### Navegación aprobada para `email_confirm`

En el paso de confirmación se aceptan únicamente números exactos:

```text
1 Sí
2 Corregir email
9 Volver a servicios
0 Cancelar
```

No se aceptan aliases textuales en este paso. Valores como `si`, `sí`, `yes`, `corregir`, `volver`, `back`, `cancelar` o `salir` deben tratarse como opción inválida mientras la sesión esté en `email_confirm`.

## Diseño de flujo

### Tenant Admin

Estado actual:

```text
service → email → awaiting_result
```

Estado propuesto:

```text
service → email → email_confirm → awaiting_result
```

#### `email`

1. Si el usuario envía `0`, cancelar como hoy.
2. Validar el texto con `validate_email(msg, required=True)`.
3. Si falla, responder `wa.tenant.codigo.invalid_email` y mantener `step=email`.
4. Si pasa, normalizar con lowercase explícito: `target_email = normalized_email.lower()`.
5. Guardar en `session.temp_data["target_email"]`.
6. Cambiar `session.step` a `email_confirm`.
7. Responder `wa.tenant.codigo.email_confirm_prompt` con `{service_label}` y `{target_email}`.

#### `email_confirm`

- `1`: confirmar email. Setear `session.temp_data["pending_lookup_intent"] = "true"`, cambiar `session.step` a `awaiting_result`, guardar sesión y responder `wa.tenant.codigo.buscando`. El handler central `_handle_tenant_console()` seguirá creando y encolando el job usando el `pending_lookup_intent` existente.
- `2`: corregir email. Remover `target_email`, cambiar `session.step` a `email`, guardar sesión y volver a responder `wa.tenant.codigo.email_prompt` usando el `service_label` actual.
- `9`: volver a servicios. Restaurar `session.step` a `service`, recomponer o conservar `codigo_effective_keys`, setear `codigo_current_page = 0`, eliminar `service_key`, `service_label`, `target_email`, `pending_lookup_intent` y `lookup_job_id`, guardar sesión y responder `wa.tenant.codigo.service_prompt`.
- `0`: cancelar. Limpiar la sesión y responder `wa.tenant.cancelled`, siguiendo el comportamiento actual del flujo Tenant Admin.
- Cualquier otro input: responder `wa.tenant.codigo.invalid_email_confirm_option` y mantener `step=email_confirm`.

### Unauth / identidad no registrada

Estado actual:

```text
service → email → awaiting_result
```

Estado propuesto:

```text
service → email → email_confirm → awaiting_result
```

#### `email`

1. Si el usuario envía `0`, cancelar y cerrar Evolution como hoy.
2. Validar el texto con `validate_email(msg, required=True)`.
3. Si falla, responder `wa.tenant.codigo.invalid_email` y mantener `step=email`.
4. Si pasa, normalizar con lowercase explícito.
5. Guardar `target_email` en `session.temp_data`.
6. Cambiar `session.step` a `email_confirm`.
7. Responder `wa.tenant.codigo.email_confirm_prompt`.
8. No crear `MailLookupJob` todavía.

#### `email_confirm`

- `1`: confirmar email. Crear y encolar el `MailLookupJob` con el `target_email` guardado, cambiar a `awaiting_result`, guardar `lookup_job_id`, devolver `lookup_job_id` y `tenant_id` en `WhatsAppConsoleResponse`.
- `2`: corregir email. Remover `target_email`, cambiar a `email`, guardar y volver al prompt de email.
- `9`: volver a servicios. Restaurar `step=service`, reconstruir lista de servicios si hace falta, limpiar `service_key`, `service_label`, `target_email` y `lookup_job_id`, guardar y responder el prompt de servicios.
- `0`: cancelar. Limpiar sesión y devolver `status="closed"`, `reply_to=close_jid` y `close_jid=close_jid` cuando `close_jid` esté disponible.
- Cualquier otro input: responder `wa.tenant.codigo.invalid_email_confirm_option`, sin crear job, y mantener `step=email_confirm`.

## i18n

Agregar keys en `backend/app/core/i18n/catalogs_en_wa.py` y `backend/app/core/i18n/catalogs_es_wa.py`.

### `wa.tenant.codigo.email_confirm_prompt`

EN:

```text
✉️ *Confirm email*

Service: *{service_label}*
Email: *{target_email}*

Is this email correct?

1️⃣ Yes
2️⃣ Correct email
9️⃣ Back to services
0️⃣ Cancel
```

ES:

```text
✉️ *Confirmar email*

Servicio: *{service_label}*
Email: *{target_email}*

¿El correo ingresado es correcto?

1️⃣ Sí
2️⃣ Corregir email
9️⃣ Volver a servicios
0️⃣ Cancelar
```

### `wa.tenant.codigo.invalid_email_confirm_option`

EN:

```text
❌ Invalid option. Reply *1* to confirm, *2* to correct the email, *9* to go back to services, or *0* to cancel.
```

ES:

```text
❌ Opción inválida. Responde *1* para confirmar, *2* para corregir el email, *9* para volver a servicios o *0* para cancelar.
```

## Archivos esperados

Implementación futura:

- `backend/app/services/whatsapp_tenant_console_service/constants.py`
- `backend/app/services/whatsapp_tenant_console_service/_const_mixin.py`
- `backend/app/services/whatsapp_tenant_console_service/_routers.py`
- `backend/app/services/whatsapp_tenant_console_service/codigo_flow.py`
- `backend/app/api/v1/endpoints/integrations/console_handlers.py`
- `backend/app/core/i18n/catalogs_en_wa.py`
- `backend/app/core/i18n/catalogs_es_wa.py`
- `backend/tests/test_whatsapp_endpoint.py`
- `backend/tests/test_tenant_console_service.py`, si se agrega cobertura unitaria directa para Tenant Admin.
- `docs/architecture/whatsapp-console-flow.md`
- `docs/architecture/input-validation-policy.md`, solo si hace falta aclarar lowercase explícito.

## Pruebas requeridas

### Unauth endpoint coverage

Actualizar `test_unregistered_identity_codigo_multistep` para que el tercer paso espere confirmación y el cuarto paso con `1` cree el job.

Agregar cobertura para:

- Email inválido responde `invalid_email` y no devuelve `lookup_job_id`.
- Email válido con mayúsculas muestra confirmación con lowercase.
- `1` en confirmación crea/enqueuea job y devuelve `lookup_job_id` + `tenant_id`.
- `2` en confirmación vuelve al prompt de email y no crea job.
- `9` en confirmación vuelve a la lista de servicios y no crea job.
- `0` en confirmación cancela, limpia sesión y devuelve `status="closed"` + `close_jid`.
- Input distinto de `1`, `2`, `9`, `0` en confirmación responde opción inválida y no crea job.

### Tenant Admin coverage

Agregar o ajustar tests para comprobar:

- El email válido pasa a `email_confirm`, no a `awaiting_result`.
- El email se guarda en lowercase.
- `pending_lookup_intent` no se setea hasta responder `1`.
- `2` vuelve a `email`.
- `9` vuelve a `service`.
- `0` cancela.
- Input inválido mantiene `email_confirm` sin crear intención de lookup.

## Criterios de aceptación

- Tenant Admin y unauth piden confirmación después de un email válido y antes de crear o marcar intención de crear lookup.
- Solo `1` desde `email_confirm` crea el lookup o marca `pending_lookup_intent`.
- `lookup_job_id` no aparece en la respuesta unauth hasta que el usuario confirma con `1`.
- Todos los emails persistidos en la sesión y enviados a `MailLookupJob` están en lowercase.
- La navegación de confirmación acepta solo `1`, `2`, `9`, `0`.
- El flujo unauth conserva cierre Evolution en cancelación con `status="closed"`, `reply_to` y `close_jid` cuando aplique.
- Los mensajes nuevos existen en EN y ES.
- No se modifica `backend/pyproject.toml`.
- No se modifica el worker de mailbox.

## Revisión de la spec

- No quedan placeholders, `TBD` ni secciones incompletas.
- El diseño separa explícitamente Tenant Admin y unauth porque hoy tienen responsabilidades distintas para crear el job.
- La navegación aprobada por el usuario está codificada sin aliases textuales.
- El alcance es suficientemente pequeño para un único plan de implementación.
- La normalización lowercase está definida tanto antes de guardar sesión como antes de crear el job.
