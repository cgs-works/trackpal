from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.database import restore_rls_context
from app.models import Plan, Service
from app.schemas.catalog import PlanCreate, PlanUpdate, ServiceCreate, ServiceUpdate


def _clean_name(name: str) -> str:
    cleaned = name.strip()
    if not cleaned:
        raise ValueError("Name is required")
    if len(cleaned) > 200:
        raise ValueError("Name must be 200 characters or fewer")
    return cleaned


class CatalogService:
    async def _commit_catalog_change(self, db: AsyncSession, conflict_message: str) -> None:
        try:
            await db.commit()
        except IntegrityError as exc:
            await db.rollback()
            raise ValueError(conflict_message) from exc

    async def list_services(self, db: AsyncSession, tenant_id: UUID) -> list[Service]:
        result = await db.execute(select(Service).where(Service.tenant_id == tenant_id).order_by(Service.created_at.desc()))
        return list(result.scalars().all())

    async def get_service(self, db: AsyncSession, tenant_id: UUID, service_id: UUID) -> Service | None:
        result = await db.execute(select(Service).where(Service.tenant_id == tenant_id, Service.id == service_id))
        return result.scalar_one_or_none()

    async def _service_name_exists(self, db: AsyncSession, tenant_id: UUID, name: str, exclude_id: UUID | None = None) -> bool:
        stmt = select(Service.id).where(Service.tenant_id == tenant_id, func.lower(Service.name) == name.lower())
        if exclude_id:
            stmt = stmt.where(Service.id != exclude_id)
        return (await db.execute(stmt)).first() is not None

    async def create_service(self, db: AsyncSession, tenant_id: UUID, payload: ServiceCreate) -> Service:
        name = _clean_name(payload.name)
        if await self._service_name_exists(db, tenant_id, name):
            raise ValueError("Service name already exists")
        service = Service(tenant_id=tenant_id, name=name)
        db.add(service)
        await self._commit_catalog_change(db, "Service name already exists")
        await restore_rls_context(db)
        await db.refresh(service)
        return service

    async def update_service(self, db: AsyncSession, tenant_id: UUID, service_id: UUID, payload: ServiceUpdate) -> Service | None:
        service = await self.get_service(db, tenant_id, service_id)
        if service is None:
            return None
        if payload.name is not None:
            name = _clean_name(payload.name)
            if await self._service_name_exists(db, tenant_id, name, service_id):
                raise ValueError("Service name already exists")
            service.name = name
        await self._commit_catalog_change(db, "Service name already exists")
        await restore_rls_context(db)
        await db.refresh(service)
        return service

    async def delete_service(self, db: AsyncSession, tenant_id: UUID, service_id: UUID) -> bool:
        service = await self.get_service(db, tenant_id, service_id)
        if service is None:
            return False
        await db.delete(service)
        await db.commit()
        return True

    async def list_plans(self, db: AsyncSession, tenant_id: UUID, service_id: UUID) -> list[Plan] | None:
        if await self.get_service(db, tenant_id, service_id) is None:
            return None
        result = await db.execute(select(Plan).where(Plan.tenant_id == tenant_id, Plan.service_id == service_id).order_by(Plan.created_at.desc()))
        return list(result.scalars().all())

    async def get_plan(self, db: AsyncSession, tenant_id: UUID, service_id: UUID, plan_id: UUID) -> Plan | None:
        result = await db.execute(select(Plan).where(Plan.tenant_id == tenant_id, Plan.service_id == service_id, Plan.id == plan_id))
        return result.scalar_one_or_none()

    async def _plan_name_exists(self, db: AsyncSession, tenant_id: UUID, service_id: UUID, name: str, exclude_id: UUID | None = None) -> bool:
        stmt = select(Plan.id).where(Plan.tenant_id == tenant_id, Plan.service_id == service_id, func.lower(Plan.name) == name.lower())
        if exclude_id:
            stmt = stmt.where(Plan.id != exclude_id)
        return (await db.execute(stmt)).first() is not None

    async def create_plan(self, db: AsyncSession, tenant_id: UUID, service_id: UUID, payload: PlanCreate) -> Plan | None:
        if await self.get_service(db, tenant_id, service_id) is None:
            return None
        name = _clean_name(payload.name)
        if await self._plan_name_exists(db, tenant_id, service_id, name):
            raise ValueError("Plan name already exists")
        plan = Plan(tenant_id=tenant_id, service_id=service_id, name=name)
        db.add(plan)
        await self._commit_catalog_change(db, "Plan name already exists")
        await restore_rls_context(db)
        await db.refresh(plan)
        return plan

    async def update_plan(self, db: AsyncSession, tenant_id: UUID, service_id: UUID, plan_id: UUID, payload: PlanUpdate) -> Plan | None:
        plan = await self.get_plan(db, tenant_id, service_id, plan_id)
        if plan is None:
            return None
        if payload.name is not None:
            name = _clean_name(payload.name)
            if await self._plan_name_exists(db, tenant_id, service_id, name, plan_id):
                raise ValueError("Plan name already exists")
            plan.name = name
        await self._commit_catalog_change(db, "Plan name already exists")
        await restore_rls_context(db)
        await db.refresh(plan)
        return plan

    async def delete_plan(self, db: AsyncSession, tenant_id: UUID, service_id: UUID, plan_id: UUID) -> bool:
        plan = await self.get_plan(db, tenant_id, service_id, plan_id)
        if plan is None:
            return False
        await db.delete(plan)
        await db.commit()
        return True
