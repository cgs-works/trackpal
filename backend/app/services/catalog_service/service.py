import math
from dataclasses import dataclass
from uuid import UUID

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import restore_rls_context
from app.core.errors import UserFacingError
from app.models import Plan, Service
from app.repositories import catalog_repository
from app.schemas.catalog import (
    CatalogDeletePagination,
    CatalogDeletePreview,
    CatalogDeleteSubscriptionRow,
    PlanCreate,
    PlanUpdate,
    ServiceCreate,
    ServiceUpdate,
)


def _clean_name(name: str) -> str:
    cleaned = name.strip()
    if not cleaned:
        raise ValueError("Name is required")
    if len(cleaned) > 200:
        raise ValueError("Name must be 200 characters or fewer")
    return cleaned


@dataclass(frozen=True)
class CatalogServiceSummary:
    id: UUID
    name: str
    plan_count: int
    active_subscription_count: int


@dataclass(frozen=True)
class CatalogPlanSummary:
    id: UUID
    service_id: UUID
    name: str
    active_subscription_count: int


class CatalogService:
    async def _commit_catalog_change(self, db: AsyncSession, err_code: str) -> None:
        try:
            await db.commit()
        except IntegrityError as exc:
            await db.rollback()
            raise UserFacingError(err_code) from exc

    # ── Internal helpers ────────────────────────────────────────────────────

    def _page_bounds(self, page: int, page_size: int) -> tuple[int, int]:
        safe_page = max(1, int(page or 1))
        safe_page_size = max(1, min(100, int(page_size or 10)))
        return safe_page, safe_page_size

    def _pagination(self, *, page: int, page_size: int, total_items: int) -> CatalogDeletePagination:
        total_pages = max(1, math.ceil(total_items / page_size))
        return CatalogDeletePagination(
            page=page,
            page_size=page_size,
            total_items=total_items,
            total_pages=total_pages,
            has_next=page < total_pages,
        )

    def _row(self, sub, client, service, plan) -> CatalogDeleteSubscriptionRow:
        return CatalogDeleteSubscriptionRow(
            id=sub.id,
            streaming_email=sub.streaming_email,
            client_name=getattr(client, "full_name", None),
            client_phone=getattr(client, "phone", None),
            service_name=service.name,
            plan_name=plan.name,
            expires_at=sub.expires_at,
        )

    # ── Service listing ─────────────────────────────────────────────────────

    async def list_services(self, db: AsyncSession, tenant_id: UUID) -> list[Service]:
        return await catalog_repository.list_services(db, tenant_id)

    async def get_service(self, db: AsyncSession, tenant_id: UUID, service_id: UUID) -> Service | None:
        return await catalog_repository.get_service(db, tenant_id, service_id)

    async def _service_name_exists(self, db: AsyncSession, tenant_id: UUID, name: str, exclude_id: UUID | None = None) -> bool:
        return await catalog_repository.service_name_exists(db, tenant_id, name, exclude_id)

    async def create_service(self, db: AsyncSession, tenant_id: UUID, payload: ServiceCreate) -> Service:
        name = _clean_name(payload.name)
        if await self._service_name_exists(db, tenant_id, name):
            raise UserFacingError("service_name_already_exists")
        service = Service(tenant_id=tenant_id, name=name)
        db.add(service)
        await self._commit_catalog_change(db, "service_name_already_exists")
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
                raise UserFacingError("service_name_already_exists")
            service.name = name
        await self._commit_catalog_change(db, "service_name_already_exists")
        await restore_rls_context(db)
        await db.refresh(service)
        return service

    # ── Plan listing ────────────────────────────────────────────────────────

    async def list_plans(self, db: AsyncSession, tenant_id: UUID, service_id: UUID) -> list[Plan] | None:
        if await self.get_service(db, tenant_id, service_id) is None:
            return None
        return await catalog_repository.list_plans(db, tenant_id, service_id)

    async def get_plan(self, db: AsyncSession, tenant_id: UUID, service_id: UUID, plan_id: UUID) -> Plan | None:
        return await catalog_repository.get_plan(db, tenant_id, service_id, plan_id)

    async def _plan_name_exists(self, db: AsyncSession, tenant_id: UUID, service_id: UUID, name: str, exclude_id: UUID | None = None) -> bool:
        return await catalog_repository.plan_name_exists(db, tenant_id, service_id, name, exclude_id)

    async def create_plan(self, db: AsyncSession, tenant_id: UUID, service_id: UUID, payload: PlanCreate) -> Plan | None:
        if await self.get_service(db, tenant_id, service_id) is None:
            return None
        name = _clean_name(payload.name)
        if await self._plan_name_exists(db, tenant_id, service_id, name):
            raise UserFacingError("plan_name_already_exists")
        plan = Plan(tenant_id=tenant_id, service_id=service_id, name=name)
        db.add(plan)
        await self._commit_catalog_change(db, "plan_name_already_exists")
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
                raise UserFacingError("plan_name_already_exists")
            plan.name = name
        await self._commit_catalog_change(db, "plan_name_already_exists")
        await restore_rls_context(db)
        await db.refresh(plan)
        return plan

    # ── Summary methods (aggregated queries, no N+1) ────────────────────────

    async def list_service_summaries(self, db: AsyncSession, tenant_id: UUID) -> list[CatalogServiceSummary]:
        """Return summaries for all services using 3 total queries (no N+1).

        Preserves alphabetical ordering via list_services.
        """
        services = await self.list_services(db, tenant_id)
        plan_counts = await catalog_repository.count_plans_for_services(db, tenant_id)
        sub_counts = await catalog_repository.count_subscriptions_for_all_services(db, tenant_id)
        return [
            CatalogServiceSummary(
                id=s.id,
                name=s.name,
                plan_count=plan_counts.get(s.id, 0),
                active_subscription_count=sub_counts.get(s.id, (0, 0))[0],
            )
            for s in services
        ]

    async def list_plan_summaries(self, db: AsyncSession, tenant_id: UUID, service_id: UUID) -> list[CatalogPlanSummary] | None:
        """Return summaries for all plans in a service using 2 total queries (no N+1).

        Preserves alphabetical ordering via list_plans.
        """
        plans = await self.list_plans(db, tenant_id, service_id)
        if plans is None:
            return None
        sub_counts = await catalog_repository.count_subscriptions_for_all_plans(db, tenant_id, service_id)
        return [
            CatalogPlanSummary(
                id=p.id,
                service_id=service_id,
                name=p.name,
                active_subscription_count=sub_counts.get(p.id, (0, 0))[0],
            )
            for p in plans
        ]

    # ── Delete preview methods ──────────────────────────────────────────────

    async def get_service_delete_preview(
        self, db: AsyncSession, tenant_id: UUID, service_id: UUID, *, page: int = 1, page_size: int = 10
    ) -> CatalogDeletePreview | None:
        service = await self.get_service(db, tenant_id, service_id)
        if service is None:
            return None
        page, page_size = self._page_bounds(page, page_size)
        offset = (page - 1) * page_size
        plan_count = await catalog_repository.count_plans_for_service(db, tenant_id, service_id)
        active_count, historical_count = await catalog_repository.count_subscriptions_for_service(db, tenant_id, service_id)
        rows = await catalog_repository.list_active_subscription_rows_for_service(
            db, tenant_id, service_id, offset=offset, limit=page_size
        )
        return CatalogDeletePreview(
            target_type="service",
            target_id=service.id,
            target_name=service.name,
            affected_plan_count=plan_count,
            active_subscription_count=active_count,
            historical_subscription_count=historical_count,
            total_subscription_count=active_count + historical_count,
            active_subscriptions=[self._row(sub, client, svc, plan) for sub, client, svc, plan in rows],
            pagination=self._pagination(page=page, page_size=page_size, total_items=active_count),
            note="frontend.catalog.delete_preview_note",
        )

    async def get_plan_delete_preview(
        self, db: AsyncSession, tenant_id: UUID, service_id: UUID, plan_id: UUID, *, page: int = 1, page_size: int = 10
    ) -> CatalogDeletePreview | None:
        plan = await self.get_plan(db, tenant_id, service_id, plan_id)
        if plan is None:
            return None
        page, page_size = self._page_bounds(page, page_size)
        offset = (page - 1) * page_size
        active_count, historical_count = await catalog_repository.count_subscriptions_for_plan(db, tenant_id, service_id, plan_id)
        rows = await catalog_repository.list_active_subscription_rows_for_plan(
            db, tenant_id, service_id, plan_id, offset=offset, limit=page_size
        )
        return CatalogDeletePreview(
            target_type="plan",
            target_id=plan.id,
            target_name=plan.name,
            affected_plan_count=0,
            active_subscription_count=active_count,
            historical_subscription_count=historical_count,
            total_subscription_count=active_count + historical_count,
            active_subscriptions=[self._row(sub, client, svc, row_plan) for sub, client, svc, row_plan in rows],
            pagination=self._pagination(page=page, page_size=page_size, total_items=active_count),
            note="frontend.catalog.delete_preview_note",
        )

    # ── Confirm-gated delete methods ────────────────────────────────────────

    async def delete_service(
        self, db: AsyncSession, tenant_id: UUID, service_id: UUID, *, confirm: bool = False
    ) -> CatalogDeletePreview | None:
        if not confirm:
            raise UserFacingError("catalog_delete_confirmation_required")
        preview = await self.get_service_delete_preview(db, tenant_id, service_id)
        if preview is None:
            return None
        service = await self.get_service(db, tenant_id, service_id)
        if service is None:
            return None
        await catalog_repository.delete_subscriptions_for_service(db, tenant_id, service_id)
        await catalog_repository.delete_plans_for_service(db, tenant_id, service_id)
        await db.delete(service)
        await self._commit_catalog_change(db, "service_delete_failed")
        return preview

    async def delete_plan(
        self, db: AsyncSession, tenant_id: UUID, service_id: UUID, plan_id: UUID, *, confirm: bool = False
    ) -> CatalogDeletePreview | None:
        if not confirm:
            raise UserFacingError("catalog_delete_confirmation_required")
        preview = await self.get_plan_delete_preview(db, tenant_id, service_id, plan_id)
        if preview is None:
            return None
        plan = await self.get_plan(db, tenant_id, service_id, plan_id)
        if plan is None:
            return None
        await catalog_repository.delete_subscriptions_for_plan(db, tenant_id, service_id, plan_id)
        await db.delete(plan)
        await self._commit_catalog_change(db, "plan_delete_failed")
        return preview
