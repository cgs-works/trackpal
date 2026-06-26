from uuid import UUID

from fastapi import APIRouter, HTTPException, Response, status

from app.api.dependencies import CurrentUser, DbDep, ProTenantId, resolve_locale
from app.core.errors import UserFacingError, translate_error
from app.core.i18n import t as _t
from app.schemas.client import ClientCreate, ClientResponse, ClientUpdate
from app.services.client_service import ClientService

router = APIRouter(prefix="/clients", tags=["clients"])
client_service = ClientService()


def _require_tenant_or_master(current_user) -> None:
    if current_user.role not in ("tenant", "master"):
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
        username=client.username,
        phone=client.phone,
        is_active=client.is_active,
        created_at=client.created_at,
        updated_at=client.updated_at,
    )


@router.get("", response_model=list[ClientResponse])
async def list_clients(db: DbDep, tenant_id: ProTenantId, current_user: CurrentUser):
    _require_tenant_or_master(current_user)
    return [
        _client_response(client)
        for client in await client_service.list_clients(db, tenant_id)
    ]


@router.post("", response_model=ClientResponse, status_code=status.HTTP_201_CREATED)
async def create_client(
    payload: ClientCreate,
    db: DbDep,
    tenant_id: ProTenantId,
    current_user: CurrentUser,
):
    _require_tenant_or_master(current_user)
    locale = await resolve_locale(db, tenant_id)
    try:
        client = await client_service.create_client(db, tenant_id, payload)
    except UserFacingError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail=translate_error(locale, exc)
        ) from exc
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail=str(exc)
        ) from exc
    if client is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=_t(locale, "errors.tenant_not_found"),
        )
    return _client_response(client)


@router.get("/{client_id}", response_model=ClientResponse)
async def get_client(
    client_id: UUID, db: DbDep, tenant_id: ProTenantId, current_user: CurrentUser
):
    _require_tenant_or_master(current_user)
    client = await client_service.get_client(db, tenant_id, client_id)
    if client is None:
        locale = await resolve_locale(db, tenant_id)
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=_t(locale, "errors.client_not_found"),
        )
    return _client_response(client)


@router.put("/{client_id}", response_model=ClientResponse)
async def update_client(
    client_id: UUID,
    payload: ClientUpdate,
    db: DbDep,
    tenant_id: ProTenantId,
    current_user: CurrentUser,
):
    _require_tenant_or_master(current_user)
    locale = await resolve_locale(db, tenant_id)
    try:
        client = await client_service.update_client(db, tenant_id, client_id, payload)
    except UserFacingError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail=translate_error(locale, exc)
        ) from exc
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail=str(exc)
        ) from exc
    if client is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=_t(locale, "errors.client_not_found"),
        )
    return _client_response(client)


@router.patch("/{client_id}/deactivate", response_model=ClientResponse)
async def deactivate_client(
    client_id: UUID, db: DbDep, tenant_id: ProTenantId, current_user: CurrentUser
):
    _require_tenant_or_master(current_user)
    client = await client_service.deactivate_client(db, tenant_id, client_id)
    if client is None:
        locale = await resolve_locale(db, tenant_id)
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=_t(locale, "errors.client_not_found"),
        )
    return _client_response(client)


@router.patch("/{client_id}/activate", response_model=ClientResponse)
async def activate_client(
    client_id: UUID, db: DbDep, tenant_id: ProTenantId, current_user: CurrentUser
):
    _require_tenant_or_master(current_user)
    client = await client_service.activate_client(db, tenant_id, client_id)
    if client is None:
        locale = await resolve_locale(db, tenant_id)
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=_t(locale, "errors.client_not_found"),
        )
    return _client_response(client)


@router.delete("/{client_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_client(
    client_id: UUID, db: DbDep, tenant_id: ProTenantId, current_user: CurrentUser
):
    _require_tenant_or_master(current_user)
    locale = await resolve_locale(db, tenant_id)
    try:
        deleted = await client_service.delete_client(db, tenant_id, client_id)
    except UserFacingError as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail=translate_error(locale, exc)
        ) from exc
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)
        ) from exc
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=_t(locale, "errors.client_not_found"),
        )
    return Response(status_code=status.HTTP_204_NO_CONTENT)
