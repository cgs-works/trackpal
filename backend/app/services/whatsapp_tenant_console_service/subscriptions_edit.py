"""Subscription edit-flow handlers for the Tenant Console."""

from __future__ import annotations


async def _handle_subscriptions_edit_field(
    self, phone, msg, session, session_service, tenant_id, db
):
    field = self.SUBSCRIPTIONS_EDIT_FIELD_MAP.get(msg)
    if field is None:
        return self._t(self.KEY_SUBSCRIPTIONS_EDIT_ERROR_INVALID_FIELD)
    if tenant_id is None or db is None:
        return self._t("wa.tenant.errors.subscription_load_failed")

    session.temp_data = {"field": field}

    if field == "client":
        if self._client_service is None:
            return self._t(self.KEY_SUBSCRIPTIONS_CLIENT_REQUIRED)
        clients = await self._client_service.list_clients(db, tenant_id)
        client_list, selection_map = self._format_client_list(clients)
        session.selection_map = selection_map
        session.step = self.SUBSCRIPTIONS_STEP_EDIT_VALUE
        if session_service is not None:
            await session_service.save_session(session)
        return self._t(
            self.KEY_SUBSCRIPTIONS_CREATE_CLIENT_PROMPT, client_list=client_list
        )

    if field == "service":
        if self._catalog_service is None:
            return self._t("wa.tenant.errors.catalog_load_failed")
        services = await self._catalog_service.list_services(db, tenant_id)
        service_list, selection_map = self._format_service_list(services)
        session.selection_map = selection_map
        session.step = self.SUBSCRIPTIONS_STEP_EDIT_VALUE
        if session_service is not None:
            await session_service.save_session(session)
        return self._t(
            self.KEY_SUBSCRIPTIONS_CREATE_SERVICE_PROMPT, service_list=service_list
        )

    if field == "plan":
        subscription = await self._get_selected_subscription(session, tenant_id, db)
        if subscription is None or self._catalog_service is None:
            return self._t(self.KEY_SUBSCRIPTIONS_INVALID_SELECTION)
        plans = (
            await self._catalog_service.list_plans(
                db, tenant_id, subscription.service_id
            )
            or []
        )
        plan_list, selection_map = self._format_plan_list(plans)
        session.selection_map = selection_map
        session.temp_data["service_id"] = str(subscription.service_id)
        session.step = self.SUBSCRIPTIONS_STEP_EDIT_VALUE
        if session_service is not None:
            await session_service.save_session(session)
        return self._t(self.KEY_SUBSCRIPTIONS_CREATE_PLAN_PROMPT, plan_list=plan_list)

    session.step = self.SUBSCRIPTIONS_STEP_EDIT_VALUE
    if session_service is not None:
        await session_service.save_session(session)
    return self._t(
        self.SUBSCRIPTIONS_EDIT_PROMPT_KEYS.get(
            field, self.KEY_SUBSCRIPTIONS_EDIT_FIELD_PROMPT
        )
    )


async def _handle_subscriptions_edit_value(
    self, phone, msg, session, session_service, tenant_id, db
):
    if tenant_id is None or db is None or self._subscription_service is None:
        return self._t("wa.tenant.errors.subscription_update_failed")
    field = session.temp_data.get("field")

    if field == "client":
        client_id = self._safe_uuid(session.selection_map.get(msg))
        if client_id is None:
            return self._t(self.KEY_SUBSCRIPTIONS_INVALID_SELECTION)
        return await self._apply_subscription_update(
            phone, session, session_service, tenant_id, db, client_id=client_id
        )

    if field == "service":
        service_id = self._safe_uuid(session.selection_map.get(msg))
        if service_id is None or self._catalog_service is None:
            return self._t(self.KEY_SUBSCRIPTIONS_INVALID_SELECTION)
        service = await self._catalog_service.get_service(db, tenant_id, service_id)
        if service is None:
            return self._t(self.KEY_SUBSCRIPTIONS_INVALID_SELECTION)
        plans = await self._catalog_service.list_plans(db, tenant_id, service_id) or []
        if not plans:
            return self._t("wa.tenant.errors.no_plans")
        plan_list, selection_map = self._format_plan_list(plans)
        session.selection_map = selection_map
        session.temp_data = {"field": "service_plan", "service_id": str(service_id)}
        session.step = self.SUBSCRIPTIONS_STEP_EDIT_VALUE
        if session_service is not None:
            await session_service.save_session(session)
        return self._t(self.KEY_SUBSCRIPTIONS_CREATE_PLAN_PROMPT, plan_list=plan_list)

    if field == "service_plan":
        plan_id = self._safe_uuid(session.selection_map.get(msg))
        service_id = self._safe_uuid(session.temp_data.get("service_id"))
        if plan_id is None or service_id is None:
            return self._t(self.KEY_SUBSCRIPTIONS_INVALID_SELECTION)
        return await self._apply_subscription_update(
            phone,
            session,
            session_service,
            tenant_id,
            db,
            service_id=service_id,
            plan_id=plan_id,
        )

    if field == "plan":
        plan_id = self._safe_uuid(session.selection_map.get(msg))
        if plan_id is None:
            return self._t(self.KEY_SUBSCRIPTIONS_INVALID_SELECTION)
        return await self._apply_subscription_update(
            phone, session, session_service, tenant_id, db, plan_id=plan_id
        )

    if field == "streaming_email":
        email = msg.strip()
        if not email:
            return self._t(self.KEY_SUBSCRIPTIONS_EMAIL_REQUIRED)
        return await self._apply_subscription_update(
            phone, session, session_service, tenant_id, db, streaming_email=email
        )

    if field == "profile_name":
        value = msg.strip()
        return await self._apply_subscription_update(
            phone,
            session,
            session_service,
            tenant_id,
            db,
            profile_name=None
            if value.lower() in self.SUBSCRIPTIONS_SKIP_WORDS
            else value,
        )

    if field == "streaming_password":
        session.temp_data["pending_value"] = (
            "" if msg.strip().lower() in self.SUBSCRIPTIONS_SKIP_WORDS else msg.strip()
        )
        session.step = self.SUBSCRIPTIONS_STEP_EDIT_PASSWORD_CONFIRM
        if session_service is not None:
            await session_service.save_session(session)
        return self._t(self.KEY_SUBSCRIPTIONS_EDIT_PASSWORD_CONFIRM_PROMPT)

    if field == "profile_pin":
        subscription = await self._get_selected_subscription(session, tenant_id, db)
        if subscription is None:
            return self._t(self.KEY_SUBSCRIPTIONS_INVALID_SELECTION)
        value = (
            "" if msg.strip().lower() in self.SUBSCRIPTIONS_SKIP_WORDS else msg.strip()
        )
        if value and not subscription.profile_name:
            return self._t(self.KEY_SUBSCRIPTIONS_CREATE_PIN_REQUIRES_PROFILE)
        session.temp_data["pending_value"] = value
        session.step = self.SUBSCRIPTIONS_STEP_EDIT_PIN_CONFIRM
        if session_service is not None:
            await session_service.save_session(session)
        return self._t(self.KEY_SUBSCRIPTIONS_EDIT_PIN_CONFIRM_PROMPT)

    return self._t(self.KEY_SUBSCRIPTIONS_INVALID_SELECTION)


async def _handle_subscriptions_edit_password_confirm(
    self, phone, msg, session, session_service, tenant_id, db
):
    pending_value = session.temp_data.get("pending_value", "")
    if msg.strip() != pending_value:
        return self._t(self.KEY_SUBSCRIPTIONS_EDIT_MISMATCH)
    return await self._apply_subscription_update(
        phone, session, session_service, tenant_id, db, streaming_password=pending_value
    )


async def _handle_subscriptions_edit_pin_confirm(
    self, phone, msg, session, session_service, tenant_id, db
):
    pending_value = session.temp_data.get("pending_value", "")
    if msg.strip() != pending_value:
        return self._t(self.KEY_SUBSCRIPTIONS_EDIT_MISMATCH)
    return await self._apply_subscription_update(
        phone, session, session_service, tenant_id, db, profile_pin=pending_value
    )
