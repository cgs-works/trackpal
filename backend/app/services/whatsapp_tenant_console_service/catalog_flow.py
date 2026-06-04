"""Catalog (service/plan) flow handlers for the Tenant Console."""

from __future__ import annotations

import math

from app.core.errors import UserFacingError, translate_error
from app.schemas.catalog import PlanCreate, PlanUpdate, ServiceCreate, ServiceUpdate
from app.services.whatsapp_navigation import is_back, is_cancel, is_next

from . import _context as ctx


def _paginate(items, page, page_size):
    """Paginate an item list."""
    safe_page = max(1, page)
    total_pages = max(1, math.ceil(len(items) / page_size))
    start = (safe_page - 1) * page_size
    return items[start:start + page_size], safe_page, total_pages




async def _catalog_menu_reply(self, tenant_id, db):
    """Return the catalog menu text (full or empty)."""
    if tenant_id is None or db is None or self._catalog_service is None:
        return self._t(self.KEY_CATALOG_EMPTY_MENU)
    services = await self._catalog_service.list_service_summaries(db, tenant_id)
    return self._t(self.KEY_CATALOG_MENU if services else self.KEY_CATALOG_EMPTY_MENU)


async def _start_catalog_flow(self, phone, session_service, tenant_id, db):
    """Start catalog flow: create session at menu step, return menu."""
    reply = await self._catalog_menu_reply(tenant_id, db)
    if session_service is not None:
        session = await session_service.get_session(f"admin:{phone}")
        if session is None:
            session = await session_service.create_session(f"admin:{phone}")
        session.flow = self.CATALOG_FLOW
        session.step = self.CATALOG_STEP_MENU
        session.selection_map = {}
        session.temp_data = {}
        await session_service.save_session(session)
    return reply


async def _set_post_action(self, phone, session_service, message):
    """Transition session to post-action step and append post-success prompt."""
    if session_service is not None:
        session = await session_service.get_session(f"admin:{phone}")
        if session is None:
            session = await session_service.create_session(f"admin:{phone}")
        session.flow = self.CATALOG_FLOW
        session.step = self.CATALOG_STEP_POST_ACTION
        session.selection_map = {}
        session.temp_data = {}
        await session_service.save_session(session)
    return message.rstrip() + self._t(self.KEY_CATALOG_POST_SUCCESS_PROMPT)


async def _show_catalog_service_list(self, phone, session, session_service, tenant_id, db, *, page=1):
    """Fetch, paginate, and display the service list."""
    if tenant_id is None or db is None or self._catalog_service is None:
        return self._t(self.KEY_CATALOG_INVALID_SELECTION)
    services = await self._catalog_service.list_service_summaries(db, tenant_id)
    page_size = self.CATALOG_PAGE_SIZE
    total_pages = max(1, math.ceil(len(services) / page_size))
    start = (page - 1) * page_size
    page_services = services[start : start + page_size]
    if not page_services:
        return self._t(self.KEY_CATALOG_INVALID_SELECTION)
    reply, selection_map = self._format_service_list(page_services, page=page, total_pages=total_pages)
    session.flow = self.CATALOG_FLOW
    session.step = self.CATALOG_STEP_SERVICE_SELECT
    session.selection_map = selection_map
    session.temp_data["catalog_page"] = page
    if session_service is not None:
        await session_service.save_session(session)
    return reply + "\n\n" + self._t(self.KEY_CATALOG_SERVICE_PROMPT)


async def _fetch_service_list(self, tenant_id, db):
    """Legacy helper kept for compatibility — returns simple service list."""
    if tenant_id is None or db is None or self._catalog_service is None:
        return None, {}
    services = await self._catalog_service.list_services(db, tenant_id)
    if not services:
        return None, {}
    # Use old-style format (no counts) for non-catalog callers (e.g. subscription create)
    # But the formatter now takes page/total_pages with defaults, so this still works.
    reply, selection_map = self._format_service_list(services)
    return reply, selection_map


async def _handle_catalog_menu(self, phone, msg, session, session_service, tenant_id, db):
    """Route inputs on the catalog main menu."""
    services = []
    if tenant_id is not None and db is not None and self._catalog_service is not None:
        services = await self._catalog_service.list_service_summaries(db, tenant_id)
    has_services = bool(services)

    if is_back(msg):
        if session_service is not None:
            await session_service.clear_session(f"admin:{phone}")
        return self._t(self.KEY_MAIN_MENU)
    if msg == "1" and has_services:
        return await self._show_catalog_service_list(phone, session, session_service, tenant_id, db, page=1)
    if msg == "1" and not has_services:
        session.step = self.CATALOG_STEP_CREATE_SERVICE_NAME
        if session_service is not None:
            await session_service.save_session(session)
        return self._t(self.KEY_CATALOG_CREATE_SERVICE_PROMPT)
    if msg == "2" and has_services:
        session.step = self.CATALOG_STEP_CREATE_SERVICE_NAME
        if session_service is not None:
            await session_service.save_session(session)
        return self._t(self.KEY_CATALOG_CREATE_SERVICE_PROMPT)
    if msg == "3" and has_services:
        return await self._show_catalog_delete_service_list(
            phone, session, session_service, tenant_id, db, page=1
        )
    return self._t(self.KEY_CATALOG_INVALID_SELECTION)


async def _handle_catalog_service_select(self, phone, msg, session, session_service, tenant_id, db):
    """Select a service from the paginated list."""
    if is_next(msg):
        page = session.temp_data.get("catalog_page", 1)
        return await self._show_catalog_service_list(phone, session, session_service, tenant_id, db, page=page + 1)
    if is_back(msg):
        # Back to catalog menu
        reply = await self._catalog_menu_reply(tenant_id, db)
        session.flow = self.CATALOG_FLOW
        session.step = self.CATALOG_STEP_MENU
        session.selection_map = {}
        session.temp_data = {}
        if session_service is not None:
            await session_service.save_session(session)
        return reply
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
    session.temp_data["service_id"] = service_id
    if session_service is not None:
        await session_service.save_session(session)
    return (
        self._format_service_detail(service) + "\n" + self._t(self.KEY_CATALOG_SERVICE_ACTIONS)
    )


async def _handle_catalog_service_action(self, phone, msg, session, session_service, tenant_id, db):
    """Route actions on a selected service."""
    service_id = session.temp_data.get("service_id")
    if not service_id:
        return self._t(self.KEY_CATALOG_INVALID_SELECTION)
    if msg == "1":
        # Edit name
        session.flow = self.CATALOG_FLOW
        session.step = self.CATALOG_STEP_EDIT_SERVICE
        if session_service is not None:
            await session_service.save_session(session)
        return self._t(self.KEY_CATALOG_SERVICE_EDIT_PROMPT)
    elif msg == "2":
        # View plans
        if tenant_id is None or db is None or self._catalog_service is None:
            return self._t(self.KEY_CATALOG_INVALID_SELECTION)
        parsed_id = self._safe_uuid(service_id)
        if parsed_id is None:
            return self._t(self.KEY_CATALOG_INVALID_SELECTION)
        plans = await self._catalog_service.list_plans(db, tenant_id, parsed_id)
        if not plans:
            # Empty plans menu
            session.flow = self.CATALOG_FLOW
            session.step = self.CATALOG_STEP_EMPTY_PLAN_MENU
            session.temp_data["service_id"] = service_id
            if session_service is not None:
                await session_service.save_session(session)
            return self._t(self.KEY_CATALOG_EMPTY_PLANS_MENU)
        page_size = self.CATALOG_PAGE_SIZE
        page = 1
        total_pages = max(1, math.ceil(len(plans) / page_size))
        start = (page - 1) * page_size
        page_plans = plans[start:start + page_size]
        reply, selection_map = self._format_plan_list(page_plans, page=page, total_pages=total_pages)
        session.flow = self.CATALOG_FLOW
        session.step = self.CATALOG_STEP_PLAN_SELECT
        session.selection_map = selection_map
        session.temp_data["service_id"] = service_id
        session.temp_data["plan_page"] = page
        if session_service is not None:
            await session_service.save_session(session)
        return reply + "\\n\\n" + self._t(self.KEY_CATALOG_PLAN_PROMPT)
    elif msg == "3":
        # Create plan
        session.flow = self.CATALOG_FLOW
        session.step = self.CATALOG_STEP_CREATE_PLAN_NAME
        session.temp_data["service_id"] = service_id
        if session_service is not None:
            await session_service.save_session(session)
        return self._t(self.KEY_CATALOG_CREATE_PLAN_PROMPT)
    elif msg == "4":
        return await self._show_catalog_delete_plan_list(
            phone, session, session_service, tenant_id, db, page=1
        )
    elif is_back(msg):
        return await self._show_catalog_service_list(phone, session, session_service, tenant_id, db, page=1)
    return self._t(self.KEY_CATALOG_INVALID_SELECTION)


async def _handle_catalog_edit_service(self, phone, msg, session, session_service, tenant_id, db):
    """Handle edit service name input."""
    name = msg.strip()
    if not name:
        return self._t(self.KEY_CATALOG_NAME_REQUIRED)
    service_id = getattr(session, "temp_data", {}).get("service_id")
    if not service_id or tenant_id is None or db is None or self._catalog_service is None:
        return self._t("wa.tenant.errors.service_update_failed")
    parsed_id = self._safe_uuid(service_id)
    if parsed_id is None:
        return self._t("wa.tenant.errors.service_update_failed")
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
    return await self._set_post_action(
        phone, session_service,
        self._t(self.KEY_CATALOG_SERVICE_EDIT_SUCCESS, name=service.name)
    )


async def _handle_catalog_plan_select(self, phone, msg, session, session_service, tenant_id, db):
    """Select a plan from the list."""
    if is_next(msg):
        page = session.temp_data.get("plan_page", 1)
        next_page = page + 1
        sid = session.temp_data.get("service_id")
        if not sid:
            return self._t(self.KEY_CATALOG_INVALID_SELECTION)
        parsed_id = self._safe_uuid(sid)
        if parsed_id is None or tenant_id is None or db is None or self._catalog_service is None:
            return self._t(self.KEY_CATALOG_INVALID_SELECTION)
        plans = await self._catalog_service.list_plans(db, tenant_id, parsed_id)
        if not plans:
            return self._t(self.KEY_CATALOG_INVALID_SELECTION)
        page_size = self.CATALOG_PAGE_SIZE
        total_pages = max(1, math.ceil(len(plans) / page_size))
        start = (next_page - 1) * page_size
        page_plans = plans[start:start + page_size]
        if not page_plans:
            return self._t(self.KEY_CATALOG_INVALID_SELECTION)
        reply, selection_map = self._format_plan_list(page_plans, page=next_page, total_pages=total_pages)
        session.flow = self.CATALOG_FLOW
        session.step = self.CATALOG_STEP_PLAN_SELECT
        session.selection_map = selection_map
        session.temp_data["plan_page"] = next_page
        session.temp_data["service_id"] = sid
        if session_service is not None:
            await session_service.save_session(session)
        return reply + "\n\n" + self._t(self.KEY_CATALOG_PLAN_PROMPT)

    if is_back(msg):
        # Go back to service detail
        service_id = session.temp_data.get("service_id")
        if service_id and db is not None and tenant_id is not None and self._catalog_service is not None:
            parsed_id = self._safe_uuid(service_id)
            if parsed_id is not None:
                service = await self._catalog_service.get_service(db, tenant_id, parsed_id)
                if service is not None:
                    session.flow = self.CATALOG_FLOW
                    session.step = self.CATALOG_STEP_SERVICE_ACTION
                    if session_service is not None:
                        await session_service.save_session(session)
                    return (
                        self._format_service_detail(service) + "\n" + self._t(self.KEY_CATALOG_SERVICE_ACTIONS)
                    )
        # Fallback: back to catalog menu
        reply = await self._catalog_menu_reply(tenant_id, db)
        session.flow = self.CATALOG_FLOW
        session.step = self.CATALOG_STEP_MENU
        session.selection_map = {}
        session.temp_data = {}
        if session_service is not None:
            await session_service.save_session(session)
        return reply
    plan_id = session.selection_map.get(msg)
    if not plan_id or tenant_id is None or db is None or self._catalog_service is None:
        return self._t(self.KEY_CATALOG_INVALID_SELECTION)
    service_id = session.temp_data.get("service_id")
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
    session.temp_data["plan_id"] = plan_id
    session.temp_data["service_id"] = service_id
    if session_service is not None:
        await session_service.save_session(session)
    return (
        self._format_plan_detail(plan) + "\n" + self._t(self.KEY_CATALOG_PLAN_ACTIONS)
    )


async def _handle_catalog_plan_action(self, phone, msg, session, session_service, tenant_id, db):
    """Route actions on a selected plan."""
    plan_id = session.temp_data.get("plan_id")
    if not plan_id:
        return self._t(self.KEY_CATALOG_INVALID_SELECTION)
    if msg == "1":
        # Edit name
        session.flow = self.CATALOG_FLOW
        session.step = self.CATALOG_STEP_EDIT_PLAN
        if session_service is not None:
            await session_service.save_session(session)
        return self._t(self.KEY_CATALOG_PLAN_EDIT_PROMPT)
    elif msg == "2":
        return await self._show_catalog_delete_plan_list(
            phone, session, session_service, tenant_id, db, page=1
        )
    elif is_back(msg):
        # Back to service detail
        service_id = session.temp_data.get("service_id")
        if service_id and db is not None and tenant_id is not None and self._catalog_service is not None:
            parsed_id = self._safe_uuid(service_id)
            if parsed_id is not None:
                service = await self._catalog_service.get_service(db, tenant_id, parsed_id)
                if service is not None:
                    session.flow = self.CATALOG_FLOW
                    session.step = self.CATALOG_STEP_SERVICE_ACTION
                    session.temp_data["service_id"] = service_id
                    if session_service is not None:
                        await session_service.save_session(session)
                    return (
                        self._format_service_detail(service) + "\n" + self._t(self.KEY_CATALOG_SERVICE_ACTIONS)
                    )
        # Fallback
        reply = await self._catalog_menu_reply(tenant_id, db)
        if session_service is not None:
            await session_service.clear_session(f"admin:{phone}")
        return self._with_main_menu(reply)
    return self._t(self.KEY_CATALOG_INVALID_SELECTION)


async def _handle_catalog_edit_plan(self, phone, msg, session, session_service, tenant_id, db):
    """Handle edit plan name input."""
    name = msg.strip()
    if not name:
        return self._t(self.KEY_CATALOG_NAME_REQUIRED)
    plan_id = getattr(session, "temp_data", {}).get("plan_id")
    service_id = session.temp_data.get("service_id")
    if not plan_id or not service_id or tenant_id is None or db is None or self._catalog_service is None:
        return self._t("wa.tenant.errors.plan_update_failed")
    parsed_service_id = self._safe_uuid(service_id)
    parsed_plan_id = self._safe_uuid(plan_id)
    if parsed_service_id is None or parsed_plan_id is None:
        return self._t("wa.tenant.errors.plan_update_failed")
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
    return await self._set_post_action(
        phone, session_service,
        self._t(self.KEY_CATALOG_PLAN_EDIT_SUCCESS, name=plan.name)
    )


async def _handle_catalog_create_service_name(self, phone, msg, session, session_service, tenant_id, db):
    """Handle create service name input."""
    name = msg.strip()
    if not name:
        return self._t(self.KEY_CATALOG_NAME_REQUIRED)
    if tenant_id is None or db is None or self._catalog_service is None:
        return self._t("wa.tenant.errors.catalog_load_failed")
    try:
        service = await self._catalog_service.create_service(
            db, tenant_id, ServiceCreate(name=name)
        )
    except UserFacingError as exc:
        return "❌ " + translate_error(ctx.get_locale(), exc)
    except ValueError as exc:
        return "❌ " + str(exc)
    if service is None:
        return self._t("wa.tenant.errors.catalog_load_failed")
    # Success → post-action prompt
    return await self._set_post_action(
        phone, session_service,
        self._t(self.KEY_CATALOG_CREATE_SERVICE_SUCCESS, name=service.name)
    )


async def _handle_catalog_create_plan_name(self, phone, msg, session, session_service, tenant_id, db):
    """Handle create plan name input."""
    name = msg.strip()
    if not name:
        return self._t(self.KEY_CATALOG_NAME_REQUIRED)
    service_id = session.temp_data.get("service_id")
    if not service_id or tenant_id is None or db is None or self._catalog_service is None:
        return self._t("wa.tenant.errors.catalog_load_failed")
    parsed_service_id = self._safe_uuid(service_id)
    if parsed_service_id is None:
        return self._t("wa.tenant.errors.catalog_load_failed")
    try:
        plan = await self._catalog_service.create_plan(
            db, tenant_id, parsed_service_id, PlanCreate(name=name)
        )
    except UserFacingError as exc:
        return "❌ " + translate_error(ctx.get_locale(), exc)
    except ValueError as exc:
        return "❌ " + str(exc)
    if plan is None:
        return self._t("wa.tenant.errors.catalog_load_failed")
    # Success → post-action prompt
    return await self._set_post_action(
        phone, session_service,
        self._t(self.KEY_CATALOG_CREATE_PLAN_SUCCESS, name=plan.name)
    )


async def _handle_catalog_empty_plan_menu(self, phone, msg, session, session_service, tenant_id, db):
    """Route inputs on the empty-plans sub-menu."""
    if msg == "1":
        # Create plan
        session.flow = self.CATALOG_FLOW
        session.step = self.CATALOG_STEP_CREATE_PLAN_NAME
        if session_service is not None:
            await session_service.save_session(session)
        return self._t(self.KEY_CATALOG_CREATE_PLAN_PROMPT)
    elif is_back(msg):
        # Back to service detail
        service_id = session.temp_data.get("service_id")
        if service_id and db is not None and tenant_id is not None and self._catalog_service is not None:
            parsed_id = self._safe_uuid(service_id)
            if parsed_id is not None:
                service = await self._catalog_service.get_service(db, tenant_id, parsed_id)
                if service is not None:
                    session.flow = self.CATALOG_FLOW
                    session.step = self.CATALOG_STEP_SERVICE_ACTION
                    session.temp_data["service_id"] = service_id
                    if session_service is not None:
                        await session_service.save_session(session)
                    return (
                        self._format_service_detail(service) + "\n" + self._t(self.KEY_CATALOG_SERVICE_ACTIONS)
                    )
        # Fallback
        reply = await self._catalog_menu_reply(tenant_id, db)
        if session_service is not None:
            await session_service.clear_session(f"admin:{phone}")
        return self._with_main_menu(reply)
    return self._t(self.KEY_CATALOG_INVALID_SELECTION)


async def _handle_catalog_post_action(self, phone, msg, session, session_service, tenant_id, db):
    """Route post-action decision: 1 = main menu, else invalid."""
    if msg == "1":
        if session_service is not None:
            await session_service.clear_session(f"admin:{phone}")
        return self._t(self.KEY_MAIN_MENU)
    return self._t(self.KEY_CATALOG_POST_SUCCESS_INVALID)
