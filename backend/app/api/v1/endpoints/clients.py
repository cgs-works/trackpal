from uuid import UUID

from fastapi import APIRouter, HTTPException, Response, status

from app.api.dependencies import ActiveTenantId, CurrentUser, DbDep
from app.schemas.client import ClientCreate, ClientResponse, ClientUpdate
from app.services.client_service import ClientService

router = APIRouter(prefix="/clients", tags=["clients"])
client_service = ClientService()


def _require_tenant_user(current_user) -> None:
    if current_user.role != "tenant":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Role 'tenant' required",
        )


def _client_response(client) -> ClientResponse:
    return ClientResponse(
        id=client.id,
        tenant_id=client.tenant_id,
        owner_user_id=client.owner_user_id,
        full_name=client.full_name,
        local_username=client.local_username,
        username=client.user.username,
        phone=client.phone,
        is_active=client.is_active,
        created_at=client.created_at,
        updated_at=client.updated_at,
    )


@router.get("", response_model=list[ClientResponse])
async def list_clients(db: DbDep, tenant_id: ActiveTenantId, current_user: CurrentUser):
    _require_tenant_user(current_user)
    return [_client_response(client) for client in await client_service.list_clients(db, tenant_id)]


@router.post("", response_model=ClientResponse, status_code=status.HTTP_201_CREATED)
async def create_client(payload: ClientCreate, db: DbDep, tenant_id: ActiveTenantId, current_user: CurrentUser):
    _require_tenant_user(current_user)
    try:
        client = await client_service.create_client(db, tenant_id, payload)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    if client is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tenant not found")
    return _client_response(client)


@router.get("/{client_id}", response_model=ClientResponse)
async def get_client(client_id: UUID, db: DbDep, tenant_id: ActiveTenantId, current_user: CurrentUser):
    _require_tenant_user(current_user)
    client = await client_service.get_client(db, tenant_id, client_id)
    if client is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Client not found")
    return _client_response(client)


@router.put("/{client_id}", response_model=ClientResponse)
async def update_client(client_id: UUID, payload: ClientUpdate, db: DbDep, tenant_id: ActiveTenantId, current_user: CurrentUser):
    _require_tenant_user(current_user)
    try:
        client = await client_service.update_client(db, tenant_id, client_id, payload)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    if client is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Client not found")
    return _client_response(client)


@router.patch("/{client_id}/deactivate", response_model=ClientResponse)
async def deactivate_client(client_id: UUID, db: DbDep, tenant_id: ActiveTenantId, current_user: CurrentUser):
    _require_tenant_user(current_user)
    client = await client_service.deactivate_client(db, tenant_id, client_id)
    if client is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Client not found")
    return _client_response(client)


@router.patch("/{client_id}/activate", response_model=ClientResponse)
async def activate_client(client_id: UUID, db: DbDep, tenant_id: ActiveTenantId, current_user: CurrentUser):
    _require_tenant_user(current_user)
    client = await client_service.activate_client(db, tenant_id, client_id)
    if client is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Client not found")
    return _client_response(client)


@router.delete("/{client_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_client(client_id: UUID, db: DbDep, tenant_id: ActiveTenantId, current_user: CurrentUser):
    _require_tenant_user(current_user)
    try:
        deleted = await client_service.delete_client(db, tenant_id, client_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Client not found")
    return Response(status_code=status.HTTP_204_NO_CONTENT)
