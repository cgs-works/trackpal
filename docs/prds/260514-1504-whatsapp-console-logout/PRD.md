# PRD: Cierre de sesión y retorno automático al menú de WhatsApp Master Console

## Problem Statement

La WhatsApp Master Console usa `0` como comando contextual, pero hoy hay ambigüedad entre cuatro casos distintos: cancelar un sub-flujo, terminar un flujo exitosamente, abandonar el login, o cerrar por completo la sesión autenticada.

Trackpal necesita que el canal WhatsApp trate esos estados con precisión. Cuando el Master ya está autenticado y ve el menú principal, `0` debe significar cierre real de sesión: limpiar estado local, cerrar la sesión autenticada y marcar la sesión Evolution como `closed` para esa instancia y ese contacto. En cambio, dentro de sub-flujos o durante login, `0` debe seguir funcionando como cancelación contextual. Además, al completar o cancelar un flujo CRUD, el sistema debe devolver el mensaje final y el menú principal en la misma respuesta, para que el usuario siempre quede orientado.

## Solution

Definir reglas contextuales para la WhatsApp Master Console:

- En menú principal autenticado, `0` ejecuta cierre completo de sesión.
- En sub-flujos CRUD, cualquier finalización exitosa o cancelación con `0` limpia la sesión de conversación y devuelve `mensaje final + MAIN_MENU` en la misma respuesta.
- En login, `0` cancela el intento actual, limpia Auth Session y Console Session, y devuelve al estado de arranque de login.

El backend seguirá siendo dueño de la sesión general. Al cerrar sesión desde menú principal, el backend limpiará `wa:auth:{phone}` y la Console Session asociada, y llamará al endpoint Evolution API de cambio de estado para marcar la sesión como `closed` en la instancia activa. n8n seguirá como transporte y no decidirá la lógica de logout ni de retorno al menú.

## User Stories

1. Como Master, quiero que `0` en menú principal cierre mi sesión de WhatsApp, para salir de la consola de forma explícita y segura.
2. Como Master, quiero que `0` en un sub-flujo solo cancele ese flujo y me devuelva al menú, para corregir una acción sin cerrar toda la consola.
3. Como Master, quiero que al completar un flujo CRUD se me muestre el mensaje final junto con el menú, para seguir navegando sin reenviar comandos.
4. Como Master, quiero que `0` durante login cancele el intento actual y limpie Auth Session y Console Session, para reiniciar el acceso sin residuos previos.
5. Como Master, quiero que al cerrar sesión se limpie mi Auth Session y mi Console Session, para que no queden estados reutilizables en Redis.
6. Como Master, quiero que al cerrar sesión la instancia Evolution quede marcada como `closed`, para que la conversación no permanezca abierta en el gateway de WhatsApp.
7. Como Master, quiero recibir una confirmación clara de cierre, para saber que la salida fue efectiva.
8. Como Master, quiero que volver a escribir `menu` después del cierre vuelva a iniciar el flujo normal, para reingresar sin residuos de sesión anterior.
9. Como Master, quiero que el cierre solo ocurra cuando ya estoy en menú principal autenticado, para evitar cerrar por accidente mientras apenas navego sub-flujos.
10. Como operador del sistema, quiero que la lógica de cierre viva en backend, para mantener n8n como transporte-only y evitar duplicar reglas en el workflow.
11. Como operador del sistema, quiero que el backend use el endpoint Evolution API correcto para cambiar estado de sesión, para mantener compatibilidad con la integración ya validada.
12. Como desarrollador, quiero que el comportamiento de `0` sea contextual al estado conversacional, para no romper los comandos globales existentes.
13. Como desarrollador, quiero que el logout no afecte otras instancias ni otros teléfonos, para que el cierre quede acotado al contacto y flujo activo.
14. Como QA, quiero cubrir menú principal, sub-flujo, login, éxito y cancelación por separado, para asegurar que `0` y el retorno al menú hacen cosas distintas según contexto.

## Modules

- **EvolutionClient** — cliente de integración para Evolution API. Interface: enviar cambio de estado de sesión para una instancia y un `remoteJid`, con estado `closed`.
- **WhatsAppAuthSessionService** — ciclo de vida de Auth Session. Interface: crear, validar y limpiar sesión autenticada; borrar auth y conversación cuando el login se cancela.
- **WhatsApp Master Console Orchestrator** — coordinación del cierre contextual. Interface: detectar estado conversacional, decidir si `0` es logout o cancelación, limpiar Auth Session y Console Session, y componer reply final.
- **WhatsApp Console Service** — resolución de comandos globales y menús. Interface: distinguir menú principal, sub-flujos y login; mantener el routing conversacional y devolver `MAIN_MENU` al cerrar o cancelar flujos CRUD.
- **n8n Transport Workflow** — transporte de mensajes sin lógica de negocio. Interface: recibir inbound WhatsApp, llamar backend, enviar reply. No decide logout ni retorno al menú.

## Implementation Decisions

- `0` no tendrá un único significado global; su efecto dependerá del estado conversacional.
- Logout real solo aplica cuando existe Auth Session válida y el usuario ya está en menú principal.
- El cierre real debe limpiar estado interno antes o junto con el cierre externo, para que no queden sesiones inconsistentes.
- El backend usará el endpoint Evolution API de cambio de estado de sesión del bot n8n con `status=closed`.
- La sesión externa se cerrará para la instancia y el contacto activo, no para toda la cuenta ni para otras instancias.
- En sub-flujos CRUD, éxito o cancelación deben devolver un solo reply con `MAIN_MENU` concatenado al mensaje final.
- En sub-flujos, `0` seguirá funcionando como cancelación local, limpieza de sesión y retorno al menú en la misma respuesta.
- En login, `0` limpiará Auth Session y Console Session y reiniciará el acceso, sin abrir menú principal.
- n8n no incorporará ramas nuevas de negocio para logout ni para composición del menú; seguirá pasando mensaje y contexto al backend.
- La respuesta debe ser relayable por n8n sin interpretación adicional ni split de mensajes.

## Testing Decisions

- Buen test = comportamiento externo por estado: mismo mensaje `0`, distinto resultado según menú principal, sub-flujo o login.
- Se debe probar que en menú principal se limpian Auth Session y Console Session.
- Se debe probar que en menú principal se invoca cambio de estado Evolution con `closed` para la instancia activa.
- Se debe probar que en sub-flujo `0` no cierra sesión Evolution y solo cancela flujo local con menú incluido en la respuesta.
- Se debe probar que en éxito de flujo CRUD la respuesta incluye mensaje final + menú.
- Se debe probar que en login `0` limpia Auth Session y Console Session y no muestra menú principal.
- Se debe probar que el reply de cierre y retorno al menú es claro y usable por n8n.
- Se debe mantener cobertura de regresión para no romper el comportamiento actual de comandos globales fuera de logout.

## Out of Scope

- Cambios al dashboard web de autenticación o logout.
- Logout por comando distinto de `0`.
- Cierre de sesión de toda la instancia Evolution.
- Cambios al modelo de autenticación web de Trackpal.
- Cambios al workflow de n8n más allá del contrato transport-only ya existente.
- Nuevas políticas de auditoría o historial de logout.
- Separar éxito/cancelación y menú en dos mensajes distintos.

## Further Notes

- Este PRD conserva la regla existente de cancelación de sub-flujos, pero separa ese comportamiento del logout real.
- La decisión central es semántica: `0` solo cierra sesión completa cuando el contexto ya es menú principal autenticado.
- La integración con Evolution API debe tratarse como parte del cierre de sesión del canal, no como una acción independiente del usuario.
- El menú principal debe reaparecer en la misma respuesta cuando un flujo CRUD termina o se cancela, para evitar estados huérfanos en conversación.
