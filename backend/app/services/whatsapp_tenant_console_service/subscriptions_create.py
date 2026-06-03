"""Subscription create-flow step handlers (client → plan selection)."""

from __future__ import annotations
from app.services.whatsapp_navigation import is_cancel, is_back, is_next

from uuid import UUID
from datetime import datetime, timezone

from app.core.errors import UserFacingError, translate_error

from . import _context as ctx


async def _start_subscriptions_create(self, phone, session, session_service, tenant_id, db):
    if tenant_id is None or db is None or self._client_service is None:
        return self._t(self.KEY_SUBSCRIPTIONS_CLIENT_REQUIRED)
    clients = await self._client_service.list_clients(db, tenant_id)
    if not clients:
        return self._t(self.KEY_SUBSCRIPTIONS_CLIENT_REQUIRED)

    client_list, selection_map = self._format_client_list(clients)
    session.flow = self.SUBSCRIPTIONS_FLOW
    session.step = self.SUBSCRIPTIONS_STEP_CREATE_CLIENT
    session.temp_data = {"starts_at": datetime.now(timezone.utc).isoformat()}
    session.selection_map = selection_map
    if session_service is not None:
        await session_service.save_session(session)
    return self._t(self.KEY_SUBSCRIPTIONS_CREATE_CLIENT_PROMPT, client_list=client_list)


async def _handle_subscriptions_create_client(self, phone, msg, session, session_service, tenant_id, db):
    del phone
    client_id = self._safe_uuid(session.selection_map.get(msg))
    if client_id is None or tenant_id is None or db is None or self._client_service is None:
        return self._t(self.KEY_SUBSCRIPTIONS_INVALID_SELECTION)
    client = await self._client_service.get_client(db, tenant_id, client_id)
    if client is None:
        return self._t(self.KEY_SUBSCRIPTIONS_INVALID_SELECTION)

    if self._catalog_service is None:
        return self._t("wa.tenant.errors.catalog_load_failed")
    services = await self._catalog_service.list_services(db, tenant_id)
    if not services:
        return self._t("wa.tenant.errors.no_services")
    service_list, selection_map = self._format_service_list(services)

    session.temp_data.update({"client_id": str(client.id), "client_name": client.full_name})
    session.selection_map = selection_map
    session.step = self.SUBSCRIPTIONS_STEP_CREATE_SERVICE
    if session_service is not None:
        await session_service.save_session(session)
    return self._t(self.KEY_SUBSCRIPTIONS_CREATE_SERVICE_PROMPT, service_list=service_list)


async def _handle_subscriptions_create_service(self, phone, msg, session, session_service, tenant_id, db):
    del phone
    service_id = self._safe_uuid(session.selection_map.get(msg))
    if service_id is None or tenant_id is None or db is None or self._catalog_service is None:
        return self._t(self.KEY_SUBSCRIPTIONS_INVALID_SELECTION)
    service = await self._catalog_service.get_service(db, tenant_id, service_id)
    if service is None:
        return self._t(self.KEY_SUBSCRIPTIONS_INVALID_SELECTION)
    plans = await self._catalog_service.list_plans(db, tenant_id, service_id) or []
    if not plans:
        return self._t("wa.tenant.errors.no_plans")
    plan_list, selection_map = self._format_plan_list(plans)

    session.temp_data.update({"service_id": str(service.id), "service_name": service.name})
    session.selection_map = selection_map
    session.step = self.SUBSCRIPTIONS_STEP_CREATE_PLAN
    if session_service is not None:
        await session_service.save_session(session)
    return self._t(self.KEY_SUBSCRIPTIONS_CREATE_PLAN_PROMPT, plan_list=plan_list)


async def _handle_subscriptions_create_plan(self, phone, msg, session, session_service, tenant_id, db):
    del phone
    plan_id = self._safe_uuid(session.selection_map.get(msg))
    service_id = self._safe_uuid(session.temp_data.get("service_id"))
    if plan_id is None or service_id is None or tenant_id is None or db is None or self._catalog_service is None:
        return self._t(self.KEY_SUBSCRIPTIONS_INVALID_SELECTION)
    plan = await self._catalog_service.get_plan(db, tenant_id, service_id, plan_id)
    if plan is None:
        return self._t(self.KEY_SUBSCRIPTIONS_INVALID_SELECTION)

    session.temp_data.update({"plan_id": str(plan.id), "plan_name": plan.name})
    session.step = self.SUBSCRIPTIONS_STEP_CREATE_EMAIL
    if session_service is not None:
        await session_service.save_session(session)
    return self._t(self.KEY_SUBSCRIPTIONS_CREATE_EMAIL_PROMPT)


async def _handle_subscriptions_create_email(self, phone, msg, session, session_service):
    del phone
    email = msg.strip()
    if not email:
        return self._t(self.KEY_SUBSCRIPTIONS_EMAIL_REQUIRED)
    session.temp_data["streaming_email"] = email
    session.step = self.SUBSCRIPTIONS_STEP_CREATE_PASSWORD
    if session_service is not None:
        await session_service.save_session(session)
    return self._t(self.KEY_SUBSCRIPTIONS_CREATE_PASSWORD_PROMPT)


async def _handle_subscriptions_create_password(self, phone, msg, session, session_service):
    del phone
    value = msg.strip()
    if value.lower() in self.SUBSCRIPTIONS_SKIP_WORDS:
        session.temp_data["streaming_password"] = None
        session.temp_data.pop("streaming_password_pending", None)
        session.step = self.SUBSCRIPTIONS_STEP_CREATE_PROFILE_OPTION
        if session_service is not None:
            await session_service.save_session(session)
        return self._t(self.KEY_SUBSCRIPTIONS_CREATE_PROFILE_OPTION_PROMPT)

    session.temp_data["streaming_password_pending"] = value
    session.step = self.SUBSCRIPTIONS_STEP_CREATE_PASSWORD_CONFIRM
    if session_service is not None:
        await session_service.save_session(session)
    return self._t(self.KEY_SUBSCRIPTIONS_CREATE_PASSWORD_CONFIRM_PROMPT)


async def _handle_subscriptions_create_password_confirm(self, phone, msg, session, session_service):
    del phone
    pending = session.temp_data.get("streaming_password_pending")
    if msg.strip() != pending:
        return self._t(self.KEY_SUBSCRIPTIONS_CREATE_PASSWORD_MISMATCH)
    session.temp_data["streaming_password"] = pending
    session.temp_data.pop("streaming_password_pending", None)
    session.step = self.SUBSCRIPTIONS_STEP_CREATE_PROFILE_OPTION
    if session_service is not None:
        await session_service.save_session(session)
    return self._t(self.KEY_SUBSCRIPTIONS_CREATE_PROFILE_OPTION_PROMPT)


async def _handle_subscriptions_create_profile_option(self, phone, msg, session, session_service):
    del phone
    value = msg.strip()
    if value == "1":
        session.step = self.SUBSCRIPTIONS_STEP_CREATE_PROFILE_NAME
        if session_service is not None:
            await session_service.save_session(session)
        return self._t(self.KEY_SUBSCRIPTIONS_CREATE_PROFILE_NAME_PROMPT)
    if value == "2":
        session.temp_data["profile_name"] = None
        session.temp_data["profile_pin"] = None
        session.temp_data.pop("profile_pin_pending", None)
        session.step = self.SUBSCRIPTIONS_STEP_CREATE_DURATION
        if session_service is not None:
            await session_service.save_session(session)
        return self._t(self.KEY_SUBSCRIPTIONS_DURATION_PROMPT)
    return self._t(self.KEY_SUBSCRIPTIONS_INVALID_SELECTION)


async def _handle_subscriptions_create_profile_name(self, phone, msg, session, session_service):
    del phone
    value = msg.strip()
    session.temp_data["profile_name"] = (
        None if value.lower() in self.SUBSCRIPTIONS_SKIP_WORDS else value
    )
    session.step = self.SUBSCRIPTIONS_STEP_CREATE_PIN
    if session_service is not None:
        await session_service.save_session(session)
    return self._t(self.KEY_SUBSCRIPTIONS_CREATE_PIN_PROMPT)


async def _handle_subscriptions_create_pin(self, phone, msg, session, session_service):
    del phone
    value = msg.strip()
    if value.lower() in self.SUBSCRIPTIONS_SKIP_WORDS:
        session.temp_data["profile_pin"] = None
        session.temp_data.pop("profile_pin_pending", None)
        session.step = self.SUBSCRIPTIONS_STEP_CREATE_DURATION
        if session_service is not None:
            await session_service.save_session(session)
        return self._t(self.KEY_SUBSCRIPTIONS_DURATION_PROMPT)

    if not session.temp_data.get("profile_name"):
        return self._t(self.KEY_SUBSCRIPTIONS_CREATE_PIN_REQUIRES_PROFILE)

    session.temp_data["profile_pin_pending"] = value
    session.step = self.SUBSCRIPTIONS_STEP_CREATE_PIN_CONFIRM
    if session_service is not None:
        await session_service.save_session(session)
    return self._t(self.KEY_SUBSCRIPTIONS_CREATE_PIN_CONFIRM_PROMPT)


async def _handle_subscriptions_create_pin_confirm(self, phone, msg, session, session_service):
    del phone
    pending = session.temp_data.get("profile_pin_pending")
    if msg.strip() != pending:
        return self._t(self.KEY_SUBSCRIPTIONS_CREATE_PIN_MISMATCH)
    session.temp_data["profile_pin"] = pending
    session.temp_data.pop("profile_pin_pending", None)
    session.step = self.SUBSCRIPTIONS_STEP_CREATE_DURATION
    if session_service is not None:
        await session_service.save_session(session)
    return self._t(self.KEY_SUBSCRIPTIONS_DURATION_PROMPT)
