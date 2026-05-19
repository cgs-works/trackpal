# Technical Design - Tenant Admin WhatsApp Console

## Protocols

```python
class ClientServiceProtocol(Protocol):
    async def list_clients(self, db: AsyncSession, tenant_id: UUID) -> list[Client]: ...
    async def get_client(self, db: AsyncSession, tenant_id: UUID, client_id: UUID) -> Client | None: ...
    async def create_client(self, db: AsyncSession, tenant_id: UUID, payload: ClientCreate) -> Client | None: ...
    async def update_client(self, db: AsyncSession, tenant_id: UUID, client_id: UUID, payload: ClientUpdate) -> Client | None: ...
    async def deactivate_client(self, db: AsyncSession, tenant_id: UUID, client_id: UUID) -> None: ...
    async def activate_client(self, db: AsyncSession, tenant_id: UUID, client_id: UUID) -> None: ...
    async def delete_client(self, db: AsyncSession, tenant_id: UUID, client_id: UUID) -> None: ...

class CatalogServiceProtocol(Protocol):
    async def list_services(self, db: AsyncSession, tenant_id: UUID) -> list[Service]: ...
    async def get_service(self, db: AsyncSession, tenant_id: UUID, service_id: UUID) -> Service | None: ...
    async def update_service(self, db: AsyncSession, tenant_id: UUID, service_id: UUID, payload: ServiceUpdate) -> Service | None: ...
    async def list_plans(self, db: AsyncSession, tenant_id: UUID, service_id: UUID) -> list[Plan]: ...
    async def get_plan(self, db: AsyncSession, tenant_id: UUID, service_id: UUID, plan_id: UUID) -> Plan | None: ...
    async def update_plan(self, db: AsyncSession, tenant_id: UUID, service_id: UUID, plan_id: UUID, payload: PlanUpdate) -> Plan | None: ...
```

## WhatsAppTenantConsoleFacade

```python
class WhatsAppTenantConsoleFacade:
    def __init__(
        self,
        console_service: WhatsAppTenantConsoleService,
        session_service: WhatsAppSessionService,
        tenant_service: TenantServiceProtocol | None = None,
    ):
        self._console_service = console_service
        self._session_service = session_service
        self._tenant_service = tenant_service
        self._auth_service = AuthService()

    async def process_message(
        self, phone: str, message: str, *, instance: str | None = None, db: AsyncSession | None = None
    ) -> str:
        # 1. Identify by phone
        identity = await self._auth_service.identify_by_phone(db, phone)
        if not identity or identity.get("role") != "tenant":
            return "No tienes una cuenta de administrador asociada a este numero."
        
        # 2. Resolve tenant_id
        tenant_id = await self._resolve_tenant_id(db, identity["user_id"])
        if not tenant_id:
            return "No tienes una cuenta de administrador asociada a este numero."
        
        # 3. Verify tenant is active
        tenant = await self._tenant_service.get_tenant(db, tenant_id)
        if not tenant or not tenant.is_active:
            return "Tu cuenta esta desactivada."
        
        # 4. Handle "0" at main menu
        if message.strip() == "0":
            session = await self._session_service.get_session(f"admin:{phone}")
            if not session or not session.flow:
                await self._session_service.clear_session(f"admin:{phone}")
                return "Sesion cerrada. Hasta luego."
        
        # 5. Delegate to service
        return await self._console_service.process_message(
            phone=phone,
            message=message,
            tenant_id=tenant_id,
            session_service=self._session_service,
        )

    async def _resolve_tenant_id(self, db: AsyncSession, user_id: UUID) -> UUID | None:
        if self._tenant_service:
            tenant = await self._tenant_service.get_tenant(db, user_id)
            return tenant.id if tenant else None
        return None
```

## WhatsAppTenantConsoleService

Flow routing states:
- `None` -> main menu
- `clients` -> clients sub-flow
- `client_create` -> create wizard
- `client_edit` -> edit flow
- `client_deactivate` -> deactivation confirmation
- `client_delete` -> deletion confirmation
- `catalog` -> catalog sub-flow
- `profile` -> profile sub-flow
- `profile_password` -> password change flow

Each flow handler follows the same pattern as the Master `WhatsAppConsoleService`:
validate -> process -> persist -> reply.

## Entry Point Change (integrations.py)

```python
@router.post("/n8n/console")
async def n8n_console(request: WhatsAppConsoleRequest, db: ApiKeyDbDep):
    phone = validate_phone(request.phone)
    
    identity = await auth_service.identify_by_phone(db, phone)
    
    if identity and identity["role"] == "master":
        return await _handle_master_console(request, db, identity)
    elif identity and identity["role"] == "tenant":
        return await _handle_tenant_console(request, db, identity)
    elif identity:
        return WhatsAppConsoleResponse(reply="Esta consola es solo para administradores.")
    else:
        return WhatsAppConsoleResponse(reply="No tienes acceso a la consola.")
```

## Redis

Key prefix: `session:admin:{phone}` (vs Master's `session:{phone}`)
No auth session keys needed.
Same `WhatsAppSessionService` with TTL of 15 minutes.

## File List

| Action | File |
|--------|------|
| Modify | `backend/app/api/v1/endpoints/integrations.py` |
| Create | `backend/app/services/whatsapp_tenant_console_facade.py` |
| Create | `backend/app/services/whatsapp_tenant_console_service.py` |
| Modify | `backend/app/services/__init__.py` |

## Test Scenarios

18 test scenarios:

1. test_facade_phone_unknown - identify_by_phone returns None
2. test_facade_tenant_inactive - tenant is inactive
3. test_facade_tenant_active - full flow, main menu returned
4. test_clients_list - clients returned and formatted
5. test_clients_list_empty - no clients -> suggestion message
6. test_clients_create_full_flow - complete wizard
7. test_clients_create_validation - invalid input in wizard -> error + reprompt
8. test_clients_edit - select field -> new value -> confirm
9. test_clients_deactivate - CONFIRMAR required
10. test_clients_delete_inactive_only - delete active client -> error
11. test_catalog_list - services listed with plans
12. test_catalog_edit_service_name - edit service name
13. test_profile_view - profile detail displayed
14. test_profile_edit_name - edit profile name
15. test_profile_change_password - full password change
16. test_zero_cancels_flow - "0" inside active flow
17. test_zero_exits_main_menu - "0" in main menu
18. test_invalid_input_reprompt - garbage input
