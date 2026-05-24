"""Subscription flow main menu, filter, select, action handlers."""

from __future__ import annotations

from uuid import UUID
from datetime import datetime, timezone

from app.core.errors import UserFacingError, translate_error

from . import _context as ctx


async def _start_subscriptions_flow(self, phone, session_service, tenant_id, db):
    if session_service is not None:
        session = await session_service.get_session(f"admin:{phone}")
        if session is None:
            session = await session_service.create_session(f"admin:{phone}")
        session.flow = self.SUBSCRIPTIONS_FLOW
        session.step = self.SUBSCRIPTIONS_STEP_MENU
        session.temp_data = {}
        await session_service.save_session(session)
    return self._t(self.KEY_SUBSCRIPTIONS_MENU)


async def _handle_subscriptions_menu(self, phone, msg, session, session_service, tenant_id, db):
    if msg == "1":
        session.step = self.SUBSCRIPTIONS_STEP_FILTER
        if session_service is not None:
            await session_service.save_session(session)
        return self._t(self.KEY_SUBSCRIPTIONS_FILTER_PROMPT)
    if msg == "2":
        return await self._start_subscriptions_create(phone, session, session_service, tenant_id, db)
    return self._t(self.KEY_SUBSCRIPTIONS_INVALID_SELECTION)


async def _handle_subscriptions_filter(self, phone, msg, session, session_service, tenant_id, db):
    del phone
    if tenant_id is None or db is None or self._subscription_service is None:
        return self._t(self.KEY_SUBSCRIPTIONS_NO_RESULTS)

    subscriptions = []
    if msg == "1":
        subscriptions = await self._subscription_service.list_subscriptions(db, tenant_id, status="active")
    elif msg == "2":
        subscriptions = await self._subscription_service.list_subscriptions(db, tenant_id, status="expired")
    elif msg == "3":
        subscriptions = await self._subscription_service.list_subscriptions(db, tenant_id, status="cancelled")
    elif msg == "4":
        active = await self._subscription_service.list_subscriptions(db, tenant_id, status="active")
        expired = await self._subscription_service.list_subscriptions(db, tenant_id, status="expired")
        cancelled = await self._subscription_service.list_subscriptions(db, tenant_id, status="cancelled")
        subscriptions = [*active, *expired, *cancelled]
    else:
        return self._t(self.KEY_SUBSCRIPTIONS_INVALID_SELECTION)

    if not subscriptions:
        return self._t(self.KEY_SUBSCRIPTIONS_NO_RESULTS) + "\n\n" + self._t(self.KEY_SUBSCRIPTIONS_FILTER_PROMPT)

    reply, selection_map = self._format_subscription_list(subscriptions)
    session.selection_map = selection_map
    session.step = self.SUBSCRIPTIONS_STEP_SELECT
    if session_service is not None:
        await session_service.save_session(session)
    return reply + "\n\n" + self._t(self.KEY_SUBSCRIPTIONS_SELECT_PROMPT)


async def _handle_subscriptions_list(self, phone, msg, session, session_service, tenant_id, db):
    return await self._handle_subscriptions_select(phone, msg, session, session_service, tenant_id, db)


async def _handle_subscriptions_select(self, phone, msg, session, session_service, tenant_id, db):
    del phone
    subscription_id = session.selection_map.get(msg)
    parsed_id = self._safe_uuid(subscription_id)
    if parsed_id is None or tenant_id is None or db is None or self._subscription_service is None:
        return self._t(self.KEY_SUBSCRIPTIONS_INVALID_SELECTION)

    subscription = await self._subscription_service.get_subscription(db, tenant_id, parsed_id)
    if subscription is None:
        return self._t(self.KEY_SUBSCRIPTIONS_INVALID_SELECTION)

    credentials = await self._subscription_service.reveal_credentials(db, tenant_id, parsed_id)
    reply = self._format_subscription_detail(subscription, credentials)
    actions = (
        self._t(self.KEY_SUBSCRIPTION_DETAIL_ACTIONS)
        if subscription.status == "cancelled"
        else self._t(self.KEY_SUBSCRIPTION_DETAIL_ACTIONS_ACTIVE)
    )

    session.selected_tenant_id = str(parsed_id)
    session.step = self.SUBSCRIPTIONS_STEP_ACTION
    if session_service is not None:
        await session_service.save_session(session)
    return reply + "\n" + actions


async def _handle_subscriptions_action(self, phone, msg, session, session_service, tenant_id, db):
    subscription = await self._get_selected_subscription(session, tenant_id, db)
    if subscription is None:
        return self._t(self.KEY_SUBSCRIPTIONS_INVALID_SELECTION)

    if msg == "1":
        session.step = self.SUBSCRIPTIONS_STEP_EDIT_FIELD
        session.temp_data = {}
        if session_service is not None:
            await session_service.save_session(session)
        return self._t(self.KEY_SUBSCRIPTIONS_EDIT_FIELD_PROMPT)

    if msg == "2":
        session.step = self.SUBSCRIPTIONS_STEP_CANCEL_CONFIRM
        if session_service is not None:
            await session_service.save_session(session)
        client_name = getattr(subscription, "client_name", None) or getattr(subscription, "client_full_name", "—")
        return self._t(self.KEY_SUBSCRIPTIONS_CANCEL_CONFIRM_TEMPLATE,
            email=subscription.streaming_email, client_name=client_name,
        )

    if msg == "3":
        session.step = self.SUBSCRIPTIONS_STEP_RENEW_DURATION
        session.temp_data = {}
        if session_service is not None:
            await session_service.save_session(session)
        return self._t(self.KEY_SUBSCRIPTIONS_RENEW_DURATION_PROMPT)

    if msg == "4" and subscription.status == "cancelled":
        session.step = self.SUBSCRIPTIONS_STEP_REACTIVATE_DURATION
        session.temp_data = {}
        if session_service is not None:
            await session_service.save_session(session)
        return self._t(self.KEY_SUBSCRIPTIONS_REACTIVATE_DURATION_PROMPT)

    return self._t(self.KEY_SUBSCRIPTIONS_INVALID_SELECTION)


async def _get_selected_subscription(self, session, tenant_id, db):
    subscription_id = self._safe_uuid(session.selected_tenant_id)
    if subscription_id is None or tenant_id is None or db is None or self._subscription_service is None:
        return None
    return await self._subscription_service.get_subscription(db, tenant_id, subscription_id)


async def _apply_subscription_update(self, phone, session, session_service, tenant_id, db, **changes):
    if tenant_id is None or db is None or self._subscription_service is None:
        return self._t("wa.tenant.errors.subscription_update_failed")
    from app.schemas.subscription import SubscriptionUpdate

    selected_id = self._safe_uuid(session.selected_tenant_id)
    if selected_id is None:
        return self._t(self.KEY_SUBSCRIPTIONS_INVALID_SELECTION)

    normalized_changes = {key: (None if value == "" else value) for key, value in changes.items()}
    try:
        updated = await self._subscription_service.update_subscription(
            db, tenant_id, selected_id, SubscriptionUpdate(**normalized_changes),
        )
    except UserFacingError as exc:
        return "❌ " + translate_error(ctx.get_locale(), exc)
    except ValueError as exc:
        return "❌ " + str(exc)
    if updated is None:
        return self._t(self.KEY_SUBSCRIPTIONS_INVALID_SELECTION)
    if session_service is not None:
        await session_service.clear_session(f"admin:{phone}")
    return self._with_main_menu(self._t(self.KEY_SUBSCRIPTIONS_EDIT_SUCCESS))
