# Tenant plan lives on tenants table

El plan de un tenant (`starter` | `pro`) se almacena directamente en la columna `tenants.plan` en lugar de en una tabla separada de entitlements.

La razón principal es simplicidad: con solo dos planes posibles y reglas de acceso estáticas (Pro-only endpoints, Starter ocultos), una tabla de entitlements agregaria JOINs innecesarios sin beneficio real. El plan se consulta en cada request de autorización via `get_pro_tenant_id`, y un campo directo es más rápido y más fácil de cachear que una relación.

**Considered options:**
- *Entitlements table*: Más flexible para planes futuros o features granulares, pero overkill para dos planes con reglas fijas. Se puede migrar si el producto crece en complejidad.
- *Feature flags por tenant*: Más granular pero más complejo de mantener y audituar.

**Consequences:**
- Agregar un tercer plan o features por-plan requiere migración + actualización del check constraint.
- Los efectos de downgrade (revocar sesiones, limpiar Redis) viven en `tenant_service.mutations` porque ahí ya ocurren los cambios de plan.
- El frontend usa `tenant_plan` solo como UI hint; la autorización real es backend.
