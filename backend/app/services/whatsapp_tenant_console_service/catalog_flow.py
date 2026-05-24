"""Catalog (service/plan) flow handlers for the Tenant Console."""

from __future__ import annotations

from app.core.errors import UserFacingError, translate_error

from . import _context as ctx


async def _start_catalog_flow(self, phone, session_service, tenant_id, db):
    reply, selection_map = await self._fetch_service_list(tenant_id, db)
    if reply is None:
        return self._with_main_menu(self._t(self.KEY_CATALOG_NO_SERVICES))
    if session_service is not None:
        session = await session_service.get_session(f"admin:{phone}")
        if session is None:
            session = await session_service.create_session(f"admin:{phone}")
        session.flow = self.CATALOG_FLOW
        session.step = self.CATALOG_STEP_SERVICE_SELECT
        session.selection_map = selection_map
        await session_service.save_session(session)
    return reply + "\n\n" + self._t(self.KEY_CATALOG_SERVICE_PROMPT)


async def _fetch_service_list(self, tenant_id, db):
    if tenant_id is None or db is None or self._catalog_service is None:
        return None, {}
    services = await self._catalog_service.list_services(db, tenant_id)
    if not services:
        return None, {}
    reply, selection_map = self._format_service_list(services)
    return reply, selection_map


async def _handle_catalog_service_select(self, phone, msg, session, session_service, tenant_id, db):
    if msg == "0":
        if session_service is not None:
            await session_service.clear_session(f"admin:{phone}")
        return self._t(self.KEY_MAIN_MENU)
    service_id = session.selection_map.get(msg)
    if not service_id or tenant_id is None or db is None or self._catalog_service is None:
        return self._t(self.KEY_CATALOG_INVALID_SELECTION)
    parsed_id = self._safe_uuid(service_id)
    if parsed_id is None:
        return self._t(self.KEY_CATALOG_INVALID_SELECTION)
    service = await self._catalog_service.get_service(db, tenant_id, parsed_id)
    if service is None:
        return self._t(self.KEY_CATALOG_INVALID_SELECTION)
    session.flow = self.CATALOG_FLOW
    session.step = self.CATALOG_STEP_SERVICE_ACTION
    session.selected_tenant_id = service_id
    if session_service is not None:
        await session_service.save_session(session)
    return (
        self._format_service_detail(service) + "\n"
        + self._t(self.KEY_CATALOG_SERVICE_ACTIONS)
    )


async def _handle_catalog_service_action(self, phone, msg, session, session_service, tenant_id, db):
    service_id = session.selected_tenant_id
    if not service_id:
        return self._t(self.KEY_CATALOG_INVALID_SELECTION)
    if msg == "1":
        session.flow = self.CATALOG_FLOW
        session.step = self.CATALOG_STEP_EDIT_SERVICE
        if session_service is not None:
            await session_service.save_session(session)
        return self._t(self.KEY_CATALOG_SERVICE_EDIT_PROMPT)
    elif msg == "2":
        if tenant_id is None or db is None or self._catalog_service is None:
            return self._t(self.KEY_CATALOG_NO_PLANS)
        parsed_id = self._safe_uuid(service_id)
        if parsed_id is None:
            return self._t(self.KEY_CATALOG_INVALID_SELECTION)
        plans = await self._catalog_service.list_plans(db, tenant_id, parsed_id)
        if not plans:
            return self._with_main_menu(self._t(self.KEY_CATALOG_NO_PLANS))
        reply, selection_map = self._format_plan_list(plans)
        session.flow = self.CATALOG_FLOW
        session.step = self.CATALOG_STEP_PLAN_SELECT
        session.selection_map = selection_map
        if session_service is not None:
            await session_service.save_session(session)
        return reply + "\n\n" + self._t(self.KEY_CATALOG_PLAN_PROMPT)
    elif msg == "0":
        if session_service is not None:
            await session_service.clear_session(f"admin:{phone}")
        return self._t(self.KEY_MAIN_MENU)
    return self._t(self.KEY_CATALOG_INVALID_SELECTION)


async def _handle_catalog_edit_service(self, phone, msg, session, session_service, tenant_id, db):
    name = msg.strip()
    if not name:
        return self._t(self.KEY_CATALOG_NAME_REQUIRED)
    service_id = session.selected_tenant_id
    if not service_id or tenant_id is None or db is None or self._catalog_service is None:
        return self._t("wa.tenant.errors.service_update_failed")
    parsed_id = self._safe_uuid(service_id)
    if parsed_id is None:
        return self._t("wa.tenant.errors.service_update_failed")
    from app.schemas.catalog import ServiceUpdate
    try:
        service = await self._catalog_service.update_service(
            db, tenant_id, parsed_id, ServiceUpdate(name=name)
        )
    except UserFacingError as exc:
        return "❌ " + translate_error(ctx.get_locale(), exc)
    except ValueError as exc:
        return "❌ " + str(exc)
    if service is None:
        return self._t("wa.tenant.errors.service_not_found")
    if session_service is not None:
        await session_service.clear_session(f"admin:{phone}")
    return self._with_main_menu(
        self._t(self.KEY_CATALOG_SERVICE_EDIT_SUCCESS, name=service.name)
    )


async def _handle_catalog_plan_select(self, phone, msg, session, session_service, tenant_id, db):
    if msg == "0":
        reply, selection_map = await self._fetch_service_list(tenant_id, db)
        if reply is None:
            if session_service is not None:
                await session_service.clear_session(f"admin:{phone}")
            return self._t(self.KEY_MAIN_MENU)
        session.flow = self.CATALOG_FLOW
        session.step = self.CATALOG_STEP_SERVICE_SELECT
        session.selection_map = selection_map
        if session_service is not None:
            await session_service.save_session(session)
        return reply + "\n\n" + self._t(self.KEY_CATALOG_SERVICE_PROMPT)
    plan_id = session.selection_map.get(msg)
    if not plan_id or tenant_id is None or db is None or self._catalog_service is None:
        return self._t(self.KEY_CATALOG_INVALID_SELECTION)
    service_id = session.selected_tenant_id
    if service_id is None:
        return self._t(self.KEY_CATALOG_INVALID_SELECTION)
    parsed_service_id = self._safe_uuid(service_id)
    parsed_plan_id = self._safe_uuid(plan_id)
    if parsed_service_id is None or parsed_plan_id is None:
        return self._t(self.KEY_CATALOG_INVALID_SELECTION)
    plan = await self._catalog_service.get_plan(db, tenant_id, parsed_service_id, parsed_plan_id)
    if plan is None:
        return self._t(self.KEY_CATALOG_INVALID_SELECTION)
    session.flow = self.CATALOG_FLOW
    session.step = self.CATALOG_STEP_PLAN_ACTION
    session.selected_tenant_id = plan_id
    if session_service is not None:
        await session_service.save_session(session)
    session.temp_data["service_id"] = service_id
    if session_service is not None:
        await session_service.save_session(session)
    return (
        self._format_plan_detail(plan) + "\n"
        + self._t(self.KEY_CATALOG_PLAN_ACTIONS)
    )


async def _handle_catalog_plan_action(self, phone, msg, session, session_service, tenant_id, db):
    plan_id = session.selected_tenant_id
    if not plan_id:
        return self._t(self.KEY_CATALOG_INVALID_SELECTION)
    if msg == "1":
        session.flow = self.CATALOG_FLOW
        session.step = self.CATALOG_STEP_EDIT_PLAN
        if session_service is not None:
            await session_service.save_session(session)
        return self._t(self.KEY_CATALOG_PLAN_EDIT_PROMPT)
    elif msg == "0":
        reply, selection_map = await self._fetch_service_list(tenant_id, db)
        if reply is None:
            if session_service is not None:
                await session_service.clear_session(f"admin:{phone}")
            return self._t(self.KEY_MAIN_MENU)
        session.flow = self.CATALOG_FLOW
        session.step = self.CATALOG_STEP_SERVICE_SELECT
        session.selection_map = selection_map
        if session_service is not None:
            await session_service.save_session(session)
        return reply + "\n\n" + self._t(self.KEY_CATALOG_SERVICE_PROMPT)
    return self._t(self.KEY_CATALOG_INVALID_SELECTION)


async def _handle_catalog_edit_plan(self, phone, msg, session, session_service, tenant_id, db):
    name = msg.strip()
    if not name:
        return self._t(self.KEY_CATALOG_NAME_REQUIRED)
    plan_id = session.selected_tenant_id
    service_id = session.temp_data.get("service_id")
    if not plan_id or not service_id or tenant_id is None or db is None or self._catalog_service is None:
        return self._t("wa.tenant.errors.plan_update_failed")
    parsed_service_id = self._safe_uuid(service_id)
    parsed_plan_id = self._safe_uuid(plan_id)
    if parsed_service_id is None or parsed_plan_id is None:
        return self._t("wa.tenant.errors.plan_update_failed")
    from app.schemas.catalog import PlanUpdate
    try:
        plan = await self._catalog_service.update_plan(
            db, tenant_id, parsed_service_id, parsed_plan_id, PlanUpdate(name=name)
        )
    except UserFacingError as exc:
        return "❌ " + translate_error(ctx.get_locale(), exc)
    except ValueError as exc:
        return "❌ " + str(exc)
    if plan is None:
        return self._t("wa.tenant.errors.plan_not_found")
    if session_service is not None:
        await session_service.clear_session(f"admin:{phone}")
    return self._with_main_menu(
        self._t(self.KEY_CATALOG_PLAN_EDIT_SUCCESS, name=plan.name)
    )
