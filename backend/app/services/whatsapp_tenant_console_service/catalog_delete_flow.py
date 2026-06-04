"""Catalog delete warning and confirmation flow handlers."""

from __future__ import annotations

from app.services.whatsapp_navigation import is_back, is_cancel, is_next

CONFIRM_WORDS = {"confirmar", "confirm"}


def _is_confirm(msg: str) -> bool:
    return msg.strip().lower() in CONFIRM_WORDS


async def _show_catalog_delete_service_list(self, phone, session, session_service, tenant_id, db, *, page=1):
    """Show service list for delete selection."""
    services = []
    if tenant_id is not None and db is not None and self._catalog_service is not None:
        services = await self._catalog_service.list_service_summaries(db, tenant_id)
    if not services:
        return await self._catalog_menu_reply(tenant_id, db)
    page_items, page, total_pages = self._paginate(services, page, self.CATALOG_PAGE_SIZE)
    reply, selection_map = self._format_service_list(page_items, page=page, total_pages=total_pages)
    session.flow = self.CATALOG_FLOW
    session.step = self.CATALOG_STEP_DELETE_SERVICE_SELECT
    session.selection_map = selection_map
    session.temp_data["catalog_page"] = str(page)
    if session_service is not None:
        await session_service.save_session(session)
    return reply + "\n\n" + self._t("wa.tenant.catalog.delete_service_prompt")


async def _handle_catalog_delete_service_select(self, phone, msg, session, session_service, tenant_id, db):
    """Handle service selection for delete."""
    # Defensive cancel guard — if routing bypasses service-level cancel
    if is_cancel(msg):
        if session_service is not None:
            await session_service.clear_session(f"admin:{phone}")
        if msg.strip() == "0":
            return self._t("wa.tenant.goodbye")
        return self._with_main_menu(self._t("wa.tenant.cancelled"))

    if is_next(msg):
        return await self._show_catalog_delete_service_list(
            phone, session, session_service, tenant_id, db,
            page=int(session.temp_data.get("catalog_page", "1")) + 1
        )
    if is_back(msg):
        session.step = self.CATALOG_STEP_MENU
        await session_service.save_session(session)
        return await self._catalog_menu_reply(tenant_id, db)
    service_id = session.selection_map.get(msg)
    parsed_service_id = self._safe_uuid(service_id)
    if parsed_service_id is None:
        return self._t(self.KEY_CATALOG_INVALID_SELECTION)
    session.step = self.CATALOG_STEP_DELETE_SERVICE_CONFIRM
    session.temp_data["delete_service_id"] = str(parsed_service_id)
    session.temp_data["delete_page"] = "1"
    await session_service.save_session(session)
    return await self._render_service_delete_warning(session, tenant_id, db, page=1)


async def _render_service_delete_warning(self, session, tenant_id, db, page=1):
    """Render service delete warning with subscription details."""
    service_id = self._safe_uuid(session.temp_data.get("delete_service_id"))
    if service_id is None or tenant_id is None or db is None or self._catalog_service is None:
        return self._t(self.KEY_CATALOG_INVALID_SELECTION)
    preview = await self._catalog_service.get_service_delete_preview(
        db, tenant_id, service_id, page=page, page_size=self.CATALOG_PAGE_SIZE
    )
    if preview is None:
        return self._t("wa.tenant.errors.service_not_found")
    plan_label = self._catalog_count("wa.tenant.catalog.count.plan", preview.affected_plan_count)
    if preview.total_subscription_count == 0:
        lines = [
            "⚠️ *Eliminar servicio*",
            "",
            self._t(
                "wa.tenant.catalog.delete_service_zero_subscriptions",
                name=preview.target_name,
                plans=plan_label,
            ),
        ]
    else:
        lines = [
            "⚠️ *Eliminar servicio*",
            "",
            f"El servicio *{preview.target_name}* tiene {plan_label} asociados.",
            f"Suscripciones activas: {preview.active_subscription_count}",
            f"Suscripciones historicas/no activas: {preview.historical_subscription_count}",
            f"Total afectado: {preview.total_subscription_count}",
            "",
            self._t("wa.tenant.catalog.delete_note"),
        ]
    if preview.active_subscriptions:
        lines.append("")
        lines.extend(
            self._format_catalog_subscription_warning_row(row)
            for row in preview.active_subscriptions
        )
    lines.extend(["", "Escribe *CONFIRMAR* para eliminar o *0* para cancelar."])
    if preview.pagination.has_next:
        lines.append(self._t("wa.nav.next"))
    lines.append(self._t("wa.nav.back"))
    return "\n".join(lines)


async def _handle_catalog_delete_service_confirm(self, phone, msg, session, session_service, tenant_id, db):
    """Handle confirm/reject for service delete."""
    # Defensive cancel guard — if routing bypasses service-level cancel
    if is_cancel(msg):
        if session_service is not None:
            await session_service.clear_session(f"admin:{phone}")
        if msg.strip() == "0":
            return self._t("wa.tenant.goodbye")
        return self._with_main_menu(self._t("wa.tenant.cancelled"))

    if is_next(msg):
        page = int(session.temp_data.get("delete_page", "1")) + 1
        session.temp_data["delete_page"] = str(page)
        await session_service.save_session(session)
        return await self._render_service_delete_warning(session, tenant_id, db, page=page)
    if is_back(msg):
        return await self._show_catalog_delete_service_list(
            phone, session, session_service, tenant_id, db, page=1
        )
    if not _is_confirm(msg):
        return self._t("wa.tenant.catalog.delete_confirm_reprompt")
    service_id = self._safe_uuid(session.temp_data.get("delete_service_id"))
    if service_id is None or tenant_id is None or db is None or self._catalog_service is None:
        return self._t(self.KEY_CATALOG_INVALID_SELECTION)
    preview = await self._catalog_service.delete_service(db, tenant_id, service_id, confirm=True)
    if preview is None:
        return self._t("wa.tenant.errors.service_not_found")
    message = self._t("wa.tenant.catalog.delete_service_success", name=preview.target_name)
    if preview.affected_plan_count or preview.total_subscription_count:
        message += self._t(
            "wa.tenant.catalog.delete_summary",
            plans=self._catalog_count("wa.tenant.catalog.count.plan", preview.affected_plan_count),
            subscriptions=self._catalog_count("wa.tenant.catalog.count.subscription", preview.total_subscription_count),
        )
    return await self._set_post_action(phone, session_service, message)


async def _show_catalog_delete_plan_list(self, phone, session, session_service, tenant_id, db, *, page=1):
    """Show plan list for delete selection."""
    service_id = self._safe_uuid(session.temp_data.get("service_id"))
    if service_id is None or tenant_id is None or db is None or self._catalog_service is None:
        return self._t(self.KEY_CATALOG_INVALID_SELECTION)
    plans = await self._catalog_service.list_plan_summaries(db, tenant_id, service_id)
    if not plans:
        session.step = self.CATALOG_STEP_MENU
        await session_service.save_session(session)
        return (
            self._t(self.KEY_CATALOG_NO_PLANS_FOR_DELETE)
            + "\n\n"
            + await self._catalog_menu_reply(tenant_id, db)
        )
    page_items, page, total_pages = self._paginate(plans, page, self.CATALOG_PAGE_SIZE)
    reply, selection_map = self._format_plan_list(page_items, page=page, total_pages=total_pages)
    session.flow = self.CATALOG_FLOW
    session.step = self.CATALOG_STEP_DELETE_PLAN_SELECT
    session.selection_map = selection_map
    session.temp_data["delete_service_id"] = str(service_id)
    session.temp_data["catalog_page"] = str(page)
    await session_service.save_session(session)
    return reply + "\n\n" + self._t("wa.tenant.catalog.delete_plan_prompt")


async def _handle_catalog_delete_plan_select(self, phone, msg, session, session_service, tenant_id, db):
    """Handle plan selection for delete."""
    # Defensive cancel guard — if routing bypasses service-level cancel
    if is_cancel(msg):
        if session_service is not None:
            await session_service.clear_session(f"admin:{phone}")
        if msg.strip() == "0":
            return self._t("wa.tenant.goodbye")
        return self._with_main_menu(self._t("wa.tenant.cancelled"))

    if is_next(msg):
        return await self._show_catalog_delete_plan_list(
            phone, session, session_service, tenant_id, db,
            page=int(session.temp_data.get("catalog_page", "1")) + 1
        )
    if is_back(msg):
        service_id = self._safe_uuid(session.temp_data.get("delete_service_id"))
        if service_id is not None and db is not None and tenant_id is not None and self._catalog_service is not None:
            service = await self._catalog_service.get_service(db, tenant_id, service_id)
            if service is not None:
                session.step = self.CATALOG_STEP_SERVICE_ACTION
                session.temp_data["service_id"] = str(service_id)
                if session_service is not None:
                    await session_service.save_session(session)
                return (
                    self._format_service_detail(service)
                    + "\n"
                    + self._t(self.KEY_CATALOG_SERVICE_ACTIONS)
                )
        session.step = self.CATALOG_STEP_MENU
        await session_service.save_session(session)
        return await self._catalog_menu_reply(tenant_id, db)
    plan_id = session.selection_map.get(msg)
    parsed_plan_id = self._safe_uuid(plan_id)
    if parsed_plan_id is None:
        return self._t(self.KEY_CATALOG_INVALID_SELECTION)
    session.step = self.CATALOG_STEP_DELETE_PLAN_CONFIRM
    session.temp_data["delete_plan_id"] = str(parsed_plan_id)
    session.temp_data["delete_page"] = "1"
    await session_service.save_session(session)
    return await self._render_plan_delete_warning(session, tenant_id, db, page=1)


async def _render_plan_delete_warning(self, session, tenant_id, db, page=1):
    """Render plan delete warning with subscription details."""
    service_id = self._safe_uuid(session.temp_data.get("delete_service_id"))
    plan_id = self._safe_uuid(session.temp_data.get("delete_plan_id"))
    if service_id is None or plan_id is None or tenant_id is None or db is None or self._catalog_service is None:
        return self._t(self.KEY_CATALOG_INVALID_SELECTION)
    preview = await self._catalog_service.get_plan_delete_preview(
        db, tenant_id, service_id, plan_id, page=page, page_size=self.CATALOG_PAGE_SIZE
    )
    if preview is None:
        return self._t("wa.tenant.errors.plan_not_found")
    if preview.total_subscription_count == 0:
        lines = [
            "⚠️ *Eliminar plan*",
            "",
            self._t("wa.tenant.catalog.delete_plan_zero_subscriptions", name=preview.target_name),
        ]
    else:
        lines = [
            "⚠️ *Eliminar plan*",
            "",
            f"El plan *{preview.target_name}* tiene suscripciones asociadas.",
            f"Suscripciones activas: {preview.active_subscription_count}",
            f"Suscripciones historicas/no activas: {preview.historical_subscription_count}",
            f"Total afectado: {preview.total_subscription_count}",
            "",
            self._t("wa.tenant.catalog.delete_note"),
        ]
    if preview.active_subscriptions:
        lines.append("")
        lines.extend(
            self._format_catalog_subscription_warning_row(row)
            for row in preview.active_subscriptions
        )
    lines.extend(["", "Escribe *CONFIRMAR* para eliminar o *0* para cancelar."])
    if preview.pagination.has_next:
        lines.append(self._t("wa.nav.next"))
    lines.append(self._t("wa.nav.back"))
    return "\n".join(lines)


async def _handle_catalog_delete_plan_confirm(self, phone, msg, session, session_service, tenant_id, db):
    """Handle confirm/reject for plan delete."""
    # Defensive cancel guard — if routing bypasses service-level cancel
    if is_cancel(msg):
        if session_service is not None:
            await session_service.clear_session(f"admin:{phone}")
        if msg.strip() == "0":
            return self._t("wa.tenant.goodbye")
        return self._with_main_menu(self._t("wa.tenant.cancelled"))

    if is_next(msg):
        page = int(session.temp_data.get("delete_page", "1")) + 1
        session.temp_data["delete_page"] = str(page)
        await session_service.save_session(session)
        return await self._render_plan_delete_warning(session, tenant_id, db, page=page)
    if is_back(msg):
        return await self._show_catalog_delete_plan_list(
            phone, session, session_service, tenant_id, db, page=1
        )
    if not _is_confirm(msg):
        return self._t("wa.tenant.catalog.delete_confirm_reprompt")
    service_id = self._safe_uuid(session.temp_data.get("delete_service_id"))
    plan_id = self._safe_uuid(session.temp_data.get("delete_plan_id"))
    if service_id is None or plan_id is None or tenant_id is None or db is None or self._catalog_service is None:
        return self._t(self.KEY_CATALOG_INVALID_SELECTION)
    preview = await self._catalog_service.delete_plan(db, tenant_id, service_id, plan_id, confirm=True)
    if preview is None:
        return self._t("wa.tenant.errors.plan_not_found")
    message = self._t("wa.tenant.catalog.delete_plan_success", name=preview.target_name)
    if preview.total_subscription_count:
        message += self._t(
            "wa.tenant.catalog.delete_summary",
            plans=self._catalog_count("wa.tenant.catalog.count.plan", 0),
            subscriptions=self._catalog_count("wa.tenant.catalog.count.subscription", preview.total_subscription_count),
        )
    return await self._set_post_action(phone, session_service, message)
