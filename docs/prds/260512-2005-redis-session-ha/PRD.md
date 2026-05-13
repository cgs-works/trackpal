# PRD: Redis de alta disponibilidad para la WhatsApp Master Console

## Problem Statement

La WhatsApp Master Console depende de estado conversacional efímero para que el Master pueda crear, editar, desactivar, reactivar y eliminar Tenants sin romper el flujo multi-paso. Hoy Redis ya es la base correcta para ese estado, pero falta definir una estrategia de alta disponibilidad y eficiencia operativa para carga alta.

Sin una estrategia explícita de pooling, failover y limpieza de datos temporales, Trackpal corre estos riesgos:

- saturar conexiones al backend de Redis bajo concurrencia alta;
- dejar sesiones huérfanas y llenar Redis con basura efímera;
- perder consistencia al hacer failover improvisado entre principal y backup;
- reintroducir flujos rotos si el estado conversacional desaparece o se degrada a modo stateless;
- mezclar formatos de phone incompatibles con la identificación del Master y el keyado de sesión.

## Solution

Definir una arquitectura Redis activa-pasiva para la WhatsApp Master Console, con Redis principal como origen normal de verdad y Redis backup como contingencia automática controlada mediante circuit breaker orientado por tráfico.

La solución debe:

- usar connection pooling por proceso para principal y backup;
- canonicalizar siempre el phone sin signo `+` y con solo dígitos;
- guardar en Redis solo estado efímero mínimo por conversación del Master;
- aplicar TTL corto y borrado explícito al finalizar cada flujo;
- hacer failover automático al backup cuando el principal falle repetidamente;
- reiniciar la sesión con mensaje claro si el backup no contiene el estado activo;
- permitir que el backup pase a TLS en el futuro sin refactor arquitectónico.

## User Stories

1. Como Master, quiero que mi conversación por WhatsApp continúe de forma estable durante operaciones multi-paso, para poder gestionar Tenants sin volver al menú por pérdida de estado.
2. Como Master, quiero que el sistema me identifique siempre con el mismo formato de phone, para que mi sesión conversacional y mi autorización no fallen por diferencias de normalización.
3. Como Master, quiero que si Redis principal falla durante una conversación, el sistema siga disponible con una contingencia clara, para no quedar bloqueado sin respuesta.
4. Como Master, quiero recibir un aviso explícito si mi sesión tuvo que reiniciarse por failover al backup, para entender por qué debo reingresar una opción en lugar de continuar desde un paso inexistente.
5. Como operador de Trackpal, quiero que Redis principal sea el backend normal y Redis backup sea contingencia, para evitar inconsistencias por doble escritura o balanceo arbitrario entre stores.
6. Como operador de Trackpal, quiero que el failover automático ocurra solo después de fallos consecutivos controlados, para evitar flapping entre principal y backup.
7. Como operador de Trackpal, quiero que la recuperación del principal ocurra por tráfico real, para mantener la solución simple y alineada con la carga efectiva del sistema.
8. Como operador de Trackpal, quiero que cada proceso del backend reutilice pools de conexiones en lugar de abrir clientes por request, para reducir latencia y evitar agotamiento de conexiones.
9. Como operador de Trackpal, quiero que las conexiones al pool se devuelvan correctamente al terminar cada operación normal, para que el sistema soporte carga alta sin fugas de recursos.
10. Como operador de Trackpal, quiero que los pipelines o recursos especiales se cierren rápido, para no dejar conexiones retenidas en escenarios de error o timeout.
11. Como operador de Trackpal, quiero que el tamaño del pool sea configurable, para poder ajustar capacidad según tráfico real sin cambiar la arquitectura.
12. Como operador de Trackpal, quiero timeouts cortos y health checks de cliente, para detectar rápido fallos de red y no bloquear workers por demasiado tiempo.
13. Como operador de Trackpal, quiero que la sesión conversacional tenga TTL de 15 minutos, para limpiar abandonos sin conservar basura más tiempo de lo necesario.
14. Como operador de Trackpal, quiero renovar el TTL solo cuando el flujo avanza de forma válida, para que Redis refleje actividad real y no ruido.
15. Como operador de Trackpal, quiero borrar explícitamente la sesión cuando el Master completa, cancela o cierra un flujo, para liberar memoria sin esperar a la expiración.
16. Como operador de Trackpal, quiero que la sesión almacene solo `flow`, `step`, `selected_tenant_id`, `temp_data` y `selection_map`, para mantener el estado mínimo y testable.
17. Como operador de Trackpal, quiero evitar guardar payloads completos de WhatsApp o listas grandes innecesarias, para que Redis siga siendo un almacén efímero y barato.
18. Como operador de Trackpal, quiero que si ambos Redis están fuera de servicio, la consola falle de forma segura con respuesta relayable, para no caer en un modo stateless roto.
19. Como operador de Trackpal, quiero soporte de configuración para backup con `redis://` o `rediss://`, para habilitar TLS futuro sin rediseñar el módulo.
20. Como equipo de desarrollo, queremos pruebas de comportamiento para pooling, failover, normalización, TTL y limpieza explícita, para evolucionar la consola sin romper disponibilidad ni consistencia.

## Modules

- **RedisConnectionManager** — administra el acceso a Redis principal y backup. Interface: inicializar pools por proceso, entregar cliente activo, aplicar circuit breaker, reintentar el principal por tráfico, cerrar recursos en shutdown.
- **PhoneNormalizer** — canonicaliza el phone de entrada para identificación y keyado de sesión. Interface: recibir valores provenientes de WhatsApp/n8n/backend y devolver solo dígitos sin `+` ni sufijos de JID.
- **WhatsAppSessionService** — administra sesión efímera del Master sobre Redis. Interface: crear, leer, actualizar, refrescar TTL y borrar explícitamente una sesión.
- **FailoverPolicy** — encapsula reglas de conmutación y recuperación. Interface: contar fallos consecutivos, abrir breaker, definir ventana de contingencia, pasar a half-open por tráfico y decidir cuándo volver al principal.
- **ContingencyReplyPolicy** — define respuestas relayables cuando hay reinicio de sesión por failover o indisponibilidad total. Interface: construir mensaje de reinicio de sesión y mensaje de consola temporalmente no disponible.
- **SessionLifecyclePolicy** — define cuándo una sesión debe crearse, renovarse, expirar o borrarse. Interface: decidir refresh de TTL, limpieza terminal y comportamiento ante sesión ausente en backup.

## Implementation Decisions

- Arquitectura activa-pasiva: Redis principal atiende operación normal; Redis backup entra solo por contingencia.
- No habrá doble escritura entre principal y backup.
- El failover será automático pero controlado por circuit breaker, no cambio de store por cada request.
- Umbral inicial recomendado: abrir breaker tras 3 fallos consecutivos del principal.
- Ventana inicial recomendada del breaker abierto: 30 a 60 segundos antes de reintentar el principal por tráfico.
- La recuperación del principal se prueba por tráfico real, no por health checks activos en segundo plano.
- Si durante failover el backup no contiene la sesión activa, la conversación se reinicia y el Master recibe mensaje claro de contingencia.
- Si principal y backup fallan, la consola responde indisponibilidad temporal; no se permite degradar a flujo stateless.
- El phone se canonicaliza siempre sin `+` y con solo dígitos, tanto para identificación del Master como para keyado de sesión.
- El valor persistido en la base de datos para phone debe seguir esa misma canonicalización sin `+`.
- La key de sesión debe basarse en ese phone canonicalizado para evitar duplicidad por formatos distintos.
- Redis principal debe usar TLS y el backup debe aceptar `redis://` o `rediss://` según configuración.
- Cada proceso del backend mantiene un pool para principal y otro para backup durante todo su ciclo de vida.
- El tamaño inicial del pool se fijará de forma conservadora, con punto de partida recomendado de 20 conexiones por pool, ajustable por configuración y métricas.
- Operaciones simples deben reutilizar el cliente global del pool; no se crearán clientes por request.
- Los datos de sesión deben limitarse al mínimo conversacional ya aceptado en la WhatsApp Master Console.
- El TTL objetivo de sesión será 15 minutos desde la última interacción válida.
- La limpieza terminal por éxito, cancelación o cierre de flujo debe usar borrado explícito además del TTL.

## Testing Decisions

- Buen test: valida comportamiento observable del Master y del operador, no detalles internos del pool o de la implementación del cliente Redis.
- Se probará que el phone siempre termine canonicalizado sin `+` ni sufijos de JID.
- Se probará que el session key use el mismo formato canonicalizado que identificación y persistencia.
- Se probará que el circuito permanezca en principal bajo operación normal y cambie a backup solo tras fallos consecutivos configurados.
- Se probará que durante failover sin sesión previa en backup el sistema responda con reinicio explícito de sesión.
- Se probará que si no hay Redis disponible el sistema falle de forma segura con respuesta relayable.
- Se probará renovación de TTL en pasos válidos y borrado explícito en éxito, cancelación y cierre terminal.
- Se probará que la sesión no conserve payloads innecesarios ni estado residual después de completar un flujo.
- Se probará que principal y backup soporten diferencias de esquema (`redis://` y `rediss://`) vía configuración.
- Se reutilizarán patrones ya existentes de pruebas de servicio, endpoint y fakes para aislar comportamiento conversacional y de integración sin depender de Redis cloud real.

## Out of Scope

- Replicación de sesiones entre principal y backup.
- Doble escritura activa en ambos Redis.
- Balanceo activo-activo entre stores.
- Persistencia permanente de estado conversacional fuera de Redis.
- Nuevos flujos de negocio del Master Console distintos a los ya definidos para Tenant CRUD.
- Observabilidad avanzada, dashboards o alerting completo más allá de criterios mínimos necesarios para operar la estrategia.
- Cambios de producto en frontend, dashboard o entidades futuras como Customer, Subscription o Service.

## Further Notes

- Se asume que la WhatsApp Master Console seguirá siendo backend-owned y que n8n continuará como transport only.
- Se asume que el backup no usa TLS hoy, pero debe poder migrar a TLS solo mediante configuración futura.
- Se asume carga alta, pero sin límite de concurrencia confirmado; por eso el tamaño inicial del pool se define como punto de partida conservador y deberá ajustarse con métricas reales.
- La estrategia prioriza consistencia de sesión y simplicidad operativa por encima de continuidad perfecta entre principal y backup.
- Un reinicio explícito de sesión durante contingencia es preferible a fingir continuidad con estado ausente o corrupto.
