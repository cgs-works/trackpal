from uuid import UUID

from fastapi import APIRouter, HTTPException, Response, status

from app.api.dependencies import ActiveTenantId, DbDep
from app.schemas.catalog import PlanCreate, PlanResponse, PlanUpdate, ServiceCreate, ServiceResponse, ServiceUpdate
from app.services.catalog_service import CatalogService

router = APIRouter(prefix="/catalog", tags=["catalog"])
catalog_service = CatalogService()


@router.get("/services", response_model=list[ServiceResponse])
async def list_services(db: DbDep, tenant_id: ActiveTenantId):
    return await catalog_service.list_services(db, tenant_id)


@router.post("/services", response_model=ServiceResponse, status_code=status.HTTP_201_CREATED)
async def create_service(payload: ServiceCreate, db: DbDep, tenant_id: ActiveTenantId):
    try:
        return await catalog_service.create_service(db, tenant_id, payload)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc


@router.get("/services/{service_id}", response_model=ServiceResponse)
async def get_service(service_id: UUID, db: DbDep, tenant_id: ActiveTenantId):
    service = await catalog_service.get_service(db, tenant_id, service_id)
    if service is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Service not found")
    return service


@router.put("/services/{service_id}", response_model=ServiceResponse)
async def update_service(service_id: UUID, payload: ServiceUpdate, db: DbDep, tenant_id: ActiveTenantId):
    try:
        service = await catalog_service.update_service(db, tenant_id, service_id, payload)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    if service is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Service not found")
    return service


@router.delete("/services/{service_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_service(service_id: UUID, db: DbDep, tenant_id: ActiveTenantId):
    if not await catalog_service.delete_service(db, tenant_id, service_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Service not found")
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/services/{service_id}/plans", response_model=list[PlanResponse])
async def list_plans(service_id: UUID, db: DbDep, tenant_id: ActiveTenantId):
    plans = await catalog_service.list_plans(db, tenant_id, service_id)
    if plans is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Service not found")
    return plans


@router.post("/services/{service_id}/plans", response_model=PlanResponse, status_code=status.HTTP_201_CREATED)
async def create_plan(service_id: UUID, payload: PlanCreate, db: DbDep, tenant_id: ActiveTenantId):
    try:
        plan = await catalog_service.create_plan(db, tenant_id, service_id, payload)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    if plan is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Service not found")
    return plan


@router.put("/services/{service_id}/plans/{plan_id}", response_model=PlanResponse)
async def update_plan(service_id: UUID, plan_id: UUID, payload: PlanUpdate, db: DbDep, tenant_id: ActiveTenantId):
    try:
        plan = await catalog_service.update_plan(db, tenant_id, service_id, plan_id, payload)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    if plan is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Plan not found")
    return plan


@router.delete("/services/{service_id}/plans/{plan_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_plan(service_id: UUID, plan_id: UUID, db: DbDep, tenant_id: ActiveTenantId):
    if not await catalog_service.delete_plan(db, tenant_id, service_id, plan_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Plan not found")
    return Response(status_code=status.HTTP_204_NO_CONTENT)
