# PRD: Autenticación por credenciales para la WhatsApp Master Console

## Problem Statement

La autenticación actual de la WhatsApp Master Console depende del phone del Master. Ese modelo ata la consola a un número específico, dificulta operar desde otro dispositivo o desde otra Evolution Instance, y vuelve frágil el acceso cuando cambia el phone o el contexto del mensaje. Además, el workflow de n8n todavía arrastra decisiones operativas que no deben vivir en el orquestador, como filtros por instancia y configuración sensible incrustada en el export.

Trackpal necesita que el acceso del Master a la consola por WhatsApp deje de depender del phone como identidad primaria y pase a depender de credenciales reales de la entidad User. El objetivo es mantener n8n como transporte, mover la decisión de autenticación al backend, y permitir que un Master use la consola desde distintos contextos de WhatsApp sin rediseñar el dashboard ni el modelo unificado de autenticación existente.

## Solution

Rediseñar la WhatsApp Master Console para que inicie en estado no autenticado y solicite `username` y `password` dentro del flujo conversacional. El backend validará las credenciales del Master contra el modelo de autenticación unificado, creará una sesión efímera autenticada en Redis asociada al phone actual, y solo entonces habilitará acceso al menú principal y a los flujos CRUD de Tenants.

n8n permanecerá como transport-only: recibe mensaje, extrae payload, llama al backend y envía la respuesta. No decidirá permisos por instancia, no resolverá identidad por sí mismo, y no persistirá sesión. El export versionado del workflow usará placeholders de configuración para evitar secretos reales en repositorio.

## User Stories

1. Como Master, quiero iniciar la conversación por WhatsApp sin depender de que mi phone esté previamente registrado como identidad operativa, para poder acceder a la consola desde otros dispositivos o instancias.
2. Como Master, quiero que la consola me pida username al entrar si no tengo sesión autenticada, para que el acceso dependa de mi User real y no del origen del mensaje.
3. Como Master, quiero ingresar mi password en el flujo y que el backend la valide, para desbloquear el menú principal solo si las credenciales son correctas.
4. Como Master, quiero que una autenticación exitosa me deje una sesión efímera ligada al phone actual durante 15 minutos, para no reescribir credenciales en cada mensaje del mismo flujo.
5. Como Master, quiero que si la sesión autenticada expira, la consola vuelva a pedir credenciales antes de mostrar el menú, para limitar exposición si el chat queda abierto.
6. Como Master, quiero que un username inválido o desconocido produzca un mensaje claro y me mantenga en el paso correcto, para poder corregirlo sin perder el flujo.
7. Como Master, quiero que un password incorrecto produzca un mensaje claro y me mantenga en el flujo de autenticación, para poder reintentar sin caer a un estado inconsistente.
8. Como operador de seguridad, quiero que múltiples fallos consecutivos de credenciales provoquen bloqueo temporal del flujo de autenticación por WhatsApp, para dificultar fuerza bruta o abuso.
9. Como Master, quiero que cuando exista bloqueo temporal por fallos, la consola me informe que debo esperar antes de reintentar, para que la UX sea explícita y no parezca una falla silenciosa.
10. Como Master, quiero que el menú principal y todo CRUD de Tenants sigan inaccesibles mientras no exista sesión autenticada válida, para evitar bypass del login conversacional.
11. Como Master, quiero que comandos globales como menú o cancelar sigan comportándose de forma consistente, para poder salir o reiniciar el flujo aun durante autenticación.
12. Como Master, quiero que la autenticación por WhatsApp funcione aunque el mensaje llegue desde distintas Evolution Instances, para que la autorización no dependa del nombre de instancia.
13. Como operador del sistema, quiero que n8n no use filtros de instancia para decidir acceso, para no bloquear futuros Masters o escenarios multi-instancia.
14. Como operador del sistema, quiero que el export versionado del workflow no incluya secretos reales, para poder compartir y versionar el flujo sin exposición credencial.
15. Como operador del sistema, quiero que la configuración sensible del workflow viva como placeholders operativos y no como valores productivos, para separar repositorio de despliegue real.
16. Como desarrollador, quiero que el backend siga siendo dueño de la lógica conversacional y de autorización, para mantener pruebas automatizadas y evitar duplicar reglas en n8n.
17. Como desarrollador, quiero que la autenticación conversacional reuse el modelo de User existente, para no introducir un segundo sistema de credenciales paralelo.
18. Como desarrollador, quiero que el flujo autenticado siga usando Redis como sesión efímera, para conservar coherencia con la arquitectura HA ya aprobada.
19. Como desarrollador, quiero que el acceso por WhatsApp quede limitado a role `master`, para no abrir accidentalmente login conversacional para Tenants en esta iteración.
20. Como producto, quiero aceptar explícitamente el trade-off de pedir password por WhatsApp en favor de flexibilidad operativa, dejando alternativas más seguras para una iteración futura.

## Modules

- **WhatsApp Authentication Flow** — estado no autenticado, solicitud de username, solicitud de password, bloqueo temporal por fallos y transición a sesión autenticada. Interface: recibir mensaje conversacional, resolver estado actual y devolver reply + actualización de sesión.
- **Authenticated Session State** — sesión efímera del Master autenticado ligada al phone actual con TTL de 15 minutos. Interface: crear, leer, renovar, invalidar y marcar estado de bloqueo temporal.
- **Credential Verification Adapter** — adaptación entre la consola conversacional y el modelo de autenticación unificado de User/Master. Interface: validar username, verificar password, confirmar role `master`, devolver identidad autenticada mínima.
- **n8n Transport Workflow** — transporte puro entre Evolution API y backend sin filtros por instancia ni secretos reales en el export. Interface: recibir payload de WhatsApp, invocar endpoint backend, reenviar respuesta.
- **Workflow Config Placeholder Layer** — encapsulación de configuración sensible del workflow mediante placeholders versionables y sustitución operativa en instancia live. Interface: exponer variables de backend URL, API key y endpoints de mensajería sin commitear secretos reales.

## Implementation Decisions

- La identidad operativa de acceso por WhatsApp deja de ser el phone del Master y pasa a ser sus credenciales de User.
- El phone sigue existiendo como contexto de transporte y como clave de sesión efímera, pero no como prueba primaria de autorización.
- n8n permanece transport-only; no decide permisos, no interpreta rol por instancia y no persiste estado conversacional.
- El filtro por instancia tipo `Is Sublify?` se elimina del diseño futuro; la autorización vive exclusivamente en backend.
- El backend mantiene propiedad total de autenticación conversacional, autorización y flujo de menú.
- La sesión autenticada queda ligada al phone actual por 15 minutos usando Redis y arquitectura HA ya aprobada.
- La expiración de 15 minutos aplica también a la sesión autenticada, no solo al estado CRUD.
- Tras autenticación exitosa, el Master entra al menú principal sin volver a escribir credenciales durante la vigencia de la sesión.
- Los fallos consecutivos de credenciales deben activar bloqueo temporal del flujo de login; la duración exacta del bloqueo se definirá en planificación técnica.
- En esta iteración se documenta comando de login; logout explícito queda fuera de scope inmediato.
- El acceso conversacional por credenciales aplica solo a role `master`; no extiende login por WhatsApp a Tenants.
- El export del workflow debe usar Placeholder Config Pattern para evitar secretos reales en repositorio.
- Se acepta explícitamente el riesgo de capturar password en WhatsApp a cambio de flexibilidad multi-dispositivo; mitigaciones más fuertes como códigos de un solo uso o vinculación por dashboard quedan para otra iniciativa.
- La validación de inputs sensibles sigue centralizada en backend; n8n no replica validaciones de username o password.

## Testing Decisions

- Buen test = comportamiento externo observable: prompts correctos, acceso denegado antes de login, autenticación exitosa, bloqueo tras fallos, expiración de sesión, y acceso permitido solo con sesión válida.
- Se deben probar módulos de flujo conversacional autenticado, sesión efímera autenticada, adaptador de verificación de credenciales y contrato n8n/backend.
- Debe existir cobertura de regresión para bypasss: acceso a menú sin login, reutilización de sesión expirada, cambio de instancia sin afectar autorización, y workflow export sin secretos reales.
- Debe cubrirse bloqueo temporal por fallos consecutivos, incluyendo mensaje relayable y recuperación posterior.
- Debe probarse que role `tenant` no obtiene acceso a la Master Console aunque sus credenciales sean válidas.
- Debe mantenerse prior art del proyecto: pruebas de servicios con dobles/fakes, pruebas del endpoint conversacional, y pruebas del workflow como transporte sin lógica de negocio.

## Out of Scope

- Rediseño hacia autenticación por código de un solo uso, token de vinculación o QR de autorización.
- Login conversacional para Tenants.
- Logout explícito, comando de estado de sesión o gestión de dispositivos confiables.
- Cambios al dashboard web de login tradicional.
- Cambios a Customer, Subscription o Service.
- Refactor amplio de Evolution API fuera de lo necesario para transporte del nuevo flujo.
- Persistencia histórica de auditoría de intentos fallidos fuera de la sesión efímera necesaria para el bloqueo temporal.

## Further Notes

- Esta PRD reemplaza el supuesto previo de “phone como identidad primaria del Master” solo dentro del canal WhatsApp.
- El modelo unificado de autenticación con User + role se mantiene; no se crea una segunda fuente de verdad para credenciales.
- La estrategia elegida prioriza rapidez operativa y flexibilidad multi-dispositivo, aceptando un costo de seguridad que deberá evaluarse de nuevo en una futura iniciativa de endurecimiento.
- El detalle exacto del umbral de fallos y la ventana de bloqueo temporal queda abierto para el plan técnico.
- La sanitización del workflow export y la eliminación del filtro por instancia forman parte del rediseño porque afectan directamente el nuevo contrato operativo del canal.
