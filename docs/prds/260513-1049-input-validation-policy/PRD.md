# PRD: Política central de validación de identidad e inputs sensibles

## Problem Statement

Trackpal hoy acepta valores inválidos o inseguros en campos sensibles durante la creación y edición de Tenants, especialmente desde la WhatsApp Master Console. El problema ya se observó en producción: un Master pudo crear un Tenant usando valores no aptos como `/menu` en campos de identidad. Esto rompe la calidad de datos, debilita el modelo de autenticación, crea ambigüedad entre comandos conversacionales y datos de negocio, y deja al sistema con reglas inconsistentes entre dashboard, API y flujo de WhatsApp.

El problema no es solo de formato. También es de arquitectura: la validación no está centralizada. Algunos campos se normalizan parcialmente, otros no se validan, y los distintos canales pueden terminar aceptando valores distintos para la misma entidad. Eso contradice la necesidad de una sola fuente de verdad backend para todo input sensible.

## Solution

Implementar una **Input Validation Policy** centralizada en backend para todos los campos sensibles de identidad y contacto usados por Trackpal. Esta política debe ser reutilizable desde dashboard, API y WhatsApp, sin duplicar reglas por canal.

La solución usará bibliotecas especializadas para los formatos más delicados:

- **Email** — validación de sintaxis + normalización con `email-validator`, sin verificación de deliverability o DNS por request.
- **Phone** — validación con `phonenumbers`, aceptando entrada interpretable como E.164, donde el prefijo `+` puede omitirse, pero el resultado debe quedar canonicalizado a solo dígitos para almacenamiento, búsqueda e identidad.

Además, se definirán reglas explícitas para otros campos sensibles:

- **Username** — solo letras minúsculas, números y `_`, máximo 20 caracteres, debe iniciar con letra.
- **Full Name** — permite letras, números y espacios; no permite espacio inicial ni final; espacios internos múltiples se colapsan a uno antes de persistir.

La validación debe ocurrir tanto en los contratos backend como en los pasos conversacionales del flujo WhatsApp, de modo que el usuario reciba feedback temprano y el sistema mantenga reglas consistentes al persistir datos.

## User Stories

1. Como **Master**, quiero que Trackpal rechace usernames inválidos al crear un Tenant, para no registrar logins ambiguos, inseguros o incompatibles con autenticación.
2. Como **Master**, quiero que un username como `/menu`, `hola mundo`, `Admin!`, `Ñandu`, o uno que exceda 20 caracteres sea rechazado con un mensaje claro.
3. Como **Master**, quiero que Trackpal acepte usernames válidos que cumplan la política acordada, para poder crear Tenants con credenciales limpias y predecibles.
4. Como **Master**, quiero que el flujo de WhatsApp detecte un username inválido antes de avanzar al siguiente paso, para no enterarme del error al final del flujo.
5. Como **Master**, quiero que si un username ya existe, el flujo permanezca en el paso correcto para corregirlo sin perder el resto de la información recolectada.
6. Como **Master**, quiero que un email inválido sea rechazado de forma consistente tanto en dashboard como en WhatsApp.
7. Como **Master**, quiero que un email válido quede normalizado antes de guardarse, para evitar inconsistencias por casing o forma textual equivalente.
8. Como **Master**, quiero que Trackpal no dependa de consultas DNS o deliverability en cada request, para que la validación de email no falle por razones de red ajenas al dato.
9. Como **Master**, quiero que un teléfono inválido o ambiguo no se acepte al crear o editar un Tenant.
10. Como **Master**, quiero poder ingresar un teléfono en formato E.164 aunque omita el prefijo `+`, para no agregar fricción innecesaria en dashboard o WhatsApp.
11. Como **Master**, quiero que el teléfono se canonicalice a solo dígitos antes de almacenarse, para que la identidad, las búsquedas y la sesión conversacional usen una forma uniforme.
12. Como **Master**, quiero que el sistema aplique la misma política de teléfono en creación, edición, seed compatible e identificación, para no introducir variantes según canal.
13. Como **Master**, quiero que el nombre completo conserve flexibilidad semántica, pero no se ensucie con whitespace inválido.
14. Como **Master**, quiero que un `full_name` con espacio inicial o final sea rechazado o corregido según política definida, para evitar basura visible en dashboard y mensajes.
15. Como **Master**, quiero que múltiples espacios internos en `full_name` se colapsen a uno, para mantener consistencia visual y de búsqueda.
16. Como **Master**, quiero que el sistema no trate comandos conversacionales como datos válidos de identidad, para que `/menu`, `0`, `cancelar` y entradas similares no terminen persistidas en campos sensibles.
17. Como **Master**, quiero que el dashboard reciba errores de validación claros y específicos por campo, para corregir rápido sin adivinar la regla.
18. Como **Master**, quiero que la WhatsApp Master Console responda con mensajes concretos por campo inválido y permanezca en el paso correcto del flujo.
19. Como **Master**, quiero que un campo opcional como email o phone pueda omitirse solo cuando el flujo y la política lo permitan explícitamente.
20. Como **Master**, quiero que los datos ya validados no se pierdan si corrijo un solo campo inválido durante un flujo multi-paso.
21. Como **Master**, quiero que crear un Tenant desde WhatsApp y desde dashboard produzca la misma forma persistida de email, phone, username y full_name.
22. Como **Operador de plataforma**, quiero que la política viva en backend y no en n8n, para que el orquestador no se convierta en dueño de reglas de negocio.
23. Como **Operador de plataforma**, quiero evitar regex caseros dispersos, para que futuras reglas se cambien en un solo lugar.
24. Como **Desarrollador**, quiero interfaces simples de validación y normalización reutilizable, para integrarlas en schemas, services y flujos conversacionales sin duplicar lógica.
25. Como **Desarrollador**, quiero distinguir entre normalización permitida y error de validación, para saber cuándo avanzar, cuándo corregir y qué mensaje mostrar.
26. Como **Desarrollador**, quiero que las reglas se apliquen antes de persistir cualquier Tenant o Master afectado, para preservar invariantes de datos.
27. Como **Desarrollador**, quiero tests que cubran entradas válidas, inválidas, límites y regresiones de WhatsApp, para evitar que vuelva el bug de aceptar comandos como username o email.
28. Como **Sistema**, quiero que los datos de identidad tengan una única representación canónica, para que autenticación, lookup, sesión y CRUD trabajen sobre los mismos invariantes.

## Modules

- **Input Validation Policy** — núcleo de reglas compartidas para campos sensibles. Interface: validadores y normalizadores explícitos para `username`, `email`, `phone` y `full_name`, con contratos que distingan valor normalizado vs error de validación.
- **Schema Validation Layer** — aplica la política central en contratos de entrada y salida de entidades relevantes. Interface: creación y actualización de payloads de Tenant y demás actores impactados por campos sensibles.
- **WhatsApp Conversation Validation Adapter** — reutiliza la política central dentro de la WhatsApp Master Console para validación por paso, reprompt y preservación de estado. Interface: validación incremental por campo y traducción a mensajes conversacionales.
- **Service Enforcement Layer** — red de seguridad para asegurar que ninguna persistencia relevante salte la política central. Interface: creación, actualización y operaciones de identidad sobre Master y Tenant.
- **Validation Error Contract** — define mensajes y categorías de error consistentes para dashboard, API y WhatsApp. Interface: errores por campo con semántica reutilizable entre canales.
- **Regression Test Suite** — valida comportamiento observable de dashboard/API/WhatsApp frente a inputs válidos e inválidos. Interface: pruebas de contratos, flujos multi-paso y canonicalización persistida.

## Implementation Decisions

- La validación será **centralizada en backend** y no distribuida por canal.
- La política cubrirá **todo campo sensible**, no solo Tenant CRUD mínimo. Esto incluye al menos `username`, `email`, `phone` y `full_name`, y podrá extenderse a otras entradas sensibles sin duplicar reglas.
- `email-validator` será la fuente de verdad para `email`, usando validación de sintaxis + normalización, sin checks de deliverability por request.
- `phonenumbers` será la fuente de verdad para `phone`, aceptando entrada interpretable como E.164 con `+` opcional y produciendo representación canonicalizada para almacenamiento y lookup.
- **Username** queda definido como: letras minúsculas, números y `_`, máximo 20 caracteres, debe iniciar con letra.
- **Full Name** queda definido como: permite letras, números y espacios; prohíbe espacio inicial/final; colapsa espacios internos múltiples a uno.
- El flujo WhatsApp no debe depender de lógica propia para decidir qué es válido; solo debe consumir la política central y mantenerse en el paso correcto cuando falle una validación.
- Se prioriza feedback temprano por campo, pero sin sacrificar la red de seguridad de service layer.
- La normalización permitida debe ocurrir de forma explícita y consistente antes de persistencia, especialmente en `email`, `phone` y `full_name`.
- Se evitarán listas negras ad hoc para comandos como `/menu`; la protección principal debe salir de reglas positivas del campo, no de excepciones conversacionales frágiles.

## Testing Decisions

- Una buena prueba valida comportamiento observable: valor aceptado, valor rechazado, valor normalizado y mensaje/step esperado; no detalles internos de implementación.
- Se probarán de forma aislada los validadores/normalizadores centrales para inputs válidos, inválidos y edge cases.
- Se probarán contratos de creación y actualización de Tenant para asegurar que dashboard y API no acepten datos fuera de política.
- Se probará la WhatsApp Master Console con cobertura de regresión: iniciar creación, ingresar nombre válido, avanzar al siguiente paso; ingresar username/email/phone inválido, permanecer en el paso correcto con mensaje claro.
- Se probará canonicalización de phone y normalización de email/full_name para garantizar persistencia uniforme.
- Se probarán límites de username: longitud máxima, primer carácter, símbolos prohibidos, slash, espacios y mayúsculas.
- Se probarán interacciones entre validación y flujo multi-paso: corrección de campo inválido sin perder datos previos.
- Se reutilizarán patrones existentes de tests async, contrato de endpoint y flujo WhatsApp del proyecto para mantener consistencia.

## Out of Scope

- Validación de deliverability real de email vía DNS/MX por request.
- Validación de nombre humano “semántico” avanzada más allá de reglas acordadas de caracteres y whitespace.
- Reglas internacionales por país para teléfonos fuera del contrato E.164 acordado.
- Refactor amplio de todos los mensajes UX del sistema fuera de errores directamente ligados a esta política.
- Cambios de permisos, auth model o lifecycle de Tenant que no estén relacionados con validación de inputs.
- Reescritura del frontend para duplicar validación rica del backend; el backend sigue siendo la única fuente de verdad.

## Further Notes

- Esta PRD nace de una regresión real observada en la WhatsApp Master Console: campos sensibles aceptaron comandos o texto no apto como si fueran identidad válida.
- La política debe servir tanto al dashboard como al flujo WhatsApp precisamente porque ambos terminan entrando por backend.
- El objetivo no es solo “rechazar basura”, sino establecer invariantes de identidad estables para autenticación, lookup, sesión y CRUD.
- Si durante implementación aparecen más campos sensibles con reglas equivalentes, deben incorporarse como extensión de la misma política, no como validaciones aisladas por módulo o canal.
