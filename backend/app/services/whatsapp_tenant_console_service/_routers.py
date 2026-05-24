"""Flow sub-routers for the Tenant Console service."""

from __future__ import annotations


async def _route_clients_flow(self, phone, msg, step, session, session_service, tenant_id, db):
    if step == self.CLIENTS_STEP_LIST:
        return await self._handle_client_list_selection(phone, msg, session, session_service, tenant_id, db)
    elif step == self.CLIENTS_STEP_SELECT:
        return await self._handle_client_select(phone, msg, session, session_service, tenant_id, db)
    elif step == self.CLIENTS_STEP_DETAIL_ACTION:
        return await self._handle_client_detail_action(phone, msg, session, session_service, tenant_id, db)
    elif step == self.CLIENTS_STEP_CREATE_FULL_NAME:
        return await self._handle_client_create_full_name(phone, msg, session, session_service)
    elif step == self.CLIENTS_STEP_CREATE_PHONE:
        return await self._handle_client_create_phone(phone, msg, session, session_service)
    elif step == self.CLIENTS_STEP_CREATE_USERNAME:
        return await self._handle_client_create_username(phone, msg, session, session_service)
    elif step == self.CLIENTS_STEP_CREATE_PASSWORD:
        return await self._handle_client_create_password(phone, msg, session, session_service)
    elif step == self.CLIENTS_STEP_CREATE_CONFIRM:
        return await self._handle_client_create_confirm(phone, msg, session, session_service, tenant_id, db)
    elif step == self.CLIENTS_STEP_EDIT_FIELD:
        return await self._handle_client_edit_field(phone, msg, session, session_service)
    elif step == self.CLIENTS_STEP_EDIT_VALUE:
        return await self._handle_client_edit_value(phone, msg, session, session_service, tenant_id, db)
    elif step == self.CLIENTS_STEP_DEACTIVATE_CONFIRM:
        return await self._handle_client_deactivate_confirm(phone, msg, session, session_service, tenant_id, db)
    elif step == self.CLIENTS_STEP_DELETE_CONFIRM:
        return await self._handle_client_delete_confirm(phone, msg, session, session_service, tenant_id, db)
    return self._t(self.KEY_FALLBACK_ACTIVE_FLOW)


async def _route_catalog_flow(self, phone, msg, step, session, session_service, tenant_id, db):
    if step == self.CATALOG_STEP_LIST:
        return self._t(self.KEY_CLIENTS_MENU)
    elif step == self.CATALOG_STEP_SERVICE_SELECT:
        return await self._handle_catalog_service_select(phone, msg, session, session_service, tenant_id, db)
    elif step == self.CATALOG_STEP_SERVICE_ACTION:
        return await self._handle_catalog_service_action(phone, msg, session, session_service, tenant_id, db)
    elif step == self.CATALOG_STEP_EDIT_SERVICE:
        return await self._handle_catalog_edit_service(phone, msg, session, session_service, tenant_id, db)
    elif step == self.CATALOG_STEP_PLAN_SELECT:
        return await self._handle_catalog_plan_select(phone, msg, session, session_service, tenant_id, db)
    elif step == self.CATALOG_STEP_PLAN_ACTION:
        return await self._handle_catalog_plan_action(phone, msg, session, session_service, tenant_id, db)
    elif step == self.CATALOG_STEP_EDIT_PLAN:
        return await self._handle_catalog_edit_plan(phone, msg, session, session_service, tenant_id, db)
    return self._t(self.KEY_FALLBACK_ACTIVE_FLOW)


async def _route_profile_flow(self, phone, msg, step, session, session_service, user_id, db):
    if step == self.PROFILE_STEP_ACTION:
        return await self._handle_profile_action(phone, msg, session, session_service, user_id, db)
    elif step == self.PROFILE_STEP_EDIT_FIELD:
        return await self._handle_profile_edit_field(phone, msg, session, session_service)
    elif step == self.PROFILE_STEP_EDIT_VALUE:
        return await self._handle_profile_edit_value(phone, msg, session, session_service, user_id, db)
    elif step == self.PROFILE_STEP_CHANGE_PASSWORD_OLD:
        return await self._handle_profile_change_password_old(phone, msg, session, session_service, user_id, db)
    elif step == self.PROFILE_STEP_CHANGE_PASSWORD_NEW:
        return await self._handle_profile_change_password_new(phone, msg, session, session_service, user_id, db)
    elif step == self.PROFILE_STEP_CHANGE_LOCALE_SELECT:
        return await self._handle_profile_change_locale_select(phone, msg, session, session_service, user_id, db)
    return self._t(self.KEY_FALLBACK_ACTIVE_FLOW)


async def _route_subscriptions_flow(self, phone, msg, step, session, session_service, tenant_id, db):
    create_steps = {
        self.SUBSCRIPTIONS_STEP_CREATE_CLIENT,
        self.SUBSCRIPTIONS_STEP_CREATE_SERVICE,
        self.SUBSCRIPTIONS_STEP_CREATE_PLAN,
        self.SUBSCRIPTIONS_STEP_CREATE_EMAIL,
        self.SUBSCRIPTIONS_STEP_CREATE_PASSWORD,
        self.SUBSCRIPTIONS_STEP_CREATE_PASSWORD_CONFIRM,
        self.SUBSCRIPTIONS_STEP_CREATE_PROFILE_OPTION,
        self.SUBSCRIPTIONS_STEP_CREATE_PROFILE_NAME,
        self.SUBSCRIPTIONS_STEP_CREATE_PIN,
        self.SUBSCRIPTIONS_STEP_CREATE_PIN_CONFIRM,
        self.SUBSCRIPTIONS_STEP_CREATE_DURATION,
        self.SUBSCRIPTIONS_STEP_CREATE_CUSTOM_DATE,
        self.SUBSCRIPTIONS_STEP_CREATE_CONFIRM,
    }
    edit_steps = {
        self.SUBSCRIPTIONS_STEP_EDIT_FIELD,
        self.SUBSCRIPTIONS_STEP_EDIT_VALUE,
        self.SUBSCRIPTIONS_STEP_EDIT_PASSWORD_CONFIRM,
        self.SUBSCRIPTIONS_STEP_EDIT_PIN_CONFIRM,
    }
    lifecycle_steps = {
        self.SUBSCRIPTIONS_STEP_CANCEL_CONFIRM,
        self.SUBSCRIPTIONS_STEP_REACTIVATE_DURATION,
        self.SUBSCRIPTIONS_STEP_REACTIVATE_CUSTOM_DATE,
        self.SUBSCRIPTIONS_STEP_REACTIVATE_CONFIRM,
        self.SUBSCRIPTIONS_STEP_RENEW_DURATION,
        self.SUBSCRIPTIONS_STEP_RENEW_CUSTOM_DATE,
        self.SUBSCRIPTIONS_STEP_RENEW_CONFIRM,
    }

    if step == self.SUBSCRIPTIONS_STEP_MENU:
        return await self._handle_subscriptions_menu(phone, msg, session, session_service, tenant_id, db)
    elif step == self.SUBSCRIPTIONS_STEP_FILTER:
        return await self._handle_subscriptions_filter(phone, msg, session, session_service, tenant_id, db)
    elif step == self.SUBSCRIPTIONS_STEP_LIST:
        return await self._handle_subscriptions_list(phone, msg, session, session_service, tenant_id, db)
    elif step == self.SUBSCRIPTIONS_STEP_SELECT:
        return await self._handle_subscriptions_select(phone, msg, session, session_service, tenant_id, db)
    elif step == self.SUBSCRIPTIONS_STEP_ACTION:
        return await self._handle_subscriptions_action(phone, msg, session, session_service, tenant_id, db)
    elif step in create_steps:
        return await _route_subscriptions_create_flow(self, phone, msg, step, session, session_service, tenant_id, db)
    elif step in edit_steps:
        return await _route_subscriptions_edit_flow(self, phone, msg, step, session, session_service, tenant_id, db)
    elif step in lifecycle_steps:
        return await _route_subscriptions_lifecycle_flow(self, phone, msg, step, session, session_service, tenant_id, db)
    return self._t(self.KEY_FALLBACK_ACTIVE_FLOW)


async def _route_subscriptions_create_flow(self, phone, msg, step, session, session_service, tenant_id, db):
    if step == self.SUBSCRIPTIONS_STEP_CREATE_CLIENT:
        return await self._handle_subscriptions_create_client(phone, msg, session, session_service, tenant_id, db)
    elif step == self.SUBSCRIPTIONS_STEP_CREATE_SERVICE:
        return await self._handle_subscriptions_create_service(phone, msg, session, session_service, tenant_id, db)
    elif step == self.SUBSCRIPTIONS_STEP_CREATE_PLAN:
        return await self._handle_subscriptions_create_plan(phone, msg, session, session_service, tenant_id, db)
    elif step == self.SUBSCRIPTIONS_STEP_CREATE_EMAIL:
        return await self._handle_subscriptions_create_email(phone, msg, session, session_service)
    elif step == self.SUBSCRIPTIONS_STEP_CREATE_PASSWORD:
        return await self._handle_subscriptions_create_password(phone, msg, session, session_service)
    elif step == self.SUBSCRIPTIONS_STEP_CREATE_PASSWORD_CONFIRM:
        return await self._handle_subscriptions_create_password_confirm(phone, msg, session, session_service)
    elif step == self.SUBSCRIPTIONS_STEP_CREATE_PROFILE_OPTION:
        return await self._handle_subscriptions_create_profile_option(phone, msg, session, session_service)
    elif step == self.SUBSCRIPTIONS_STEP_CREATE_PROFILE_NAME:
        return await self._handle_subscriptions_create_profile_name(phone, msg, session, session_service)
    elif step == self.SUBSCRIPTIONS_STEP_CREATE_PIN:
        return await self._handle_subscriptions_create_pin(phone, msg, session, session_service)
    elif step == self.SUBSCRIPTIONS_STEP_CREATE_PIN_CONFIRM:
        return await self._handle_subscriptions_create_pin_confirm(phone, msg, session, session_service)
    elif step == self.SUBSCRIPTIONS_STEP_CREATE_DURATION:
        return await self._handle_subscriptions_create_duration(phone, msg, session, session_service, tenant_id, db)
    elif step == self.SUBSCRIPTIONS_STEP_CREATE_CUSTOM_DATE:
        return await self._handle_subscriptions_create_custom_date(phone, msg, session, session_service, tenant_id, db)
    elif step == self.SUBSCRIPTIONS_STEP_CREATE_CONFIRM:
        return await self._handle_subscriptions_create_confirm(phone, msg, session, session_service, tenant_id, db)
    return self._t(self.KEY_FALLBACK_ACTIVE_FLOW)


async def _route_subscriptions_edit_flow(self, phone, msg, step, session, session_service, tenant_id, db):
    if step == self.SUBSCRIPTIONS_STEP_EDIT_FIELD:
        return await self._handle_subscriptions_edit_field(phone, msg, session, session_service, tenant_id, db)
    elif step == self.SUBSCRIPTIONS_STEP_EDIT_VALUE:
        return await self._handle_subscriptions_edit_value(phone, msg, session, session_service, tenant_id, db)
    elif step == self.SUBSCRIPTIONS_STEP_EDIT_PASSWORD_CONFIRM:
        return await self._handle_subscriptions_edit_password_confirm(phone, msg, session, session_service, tenant_id, db)
    elif step == self.SUBSCRIPTIONS_STEP_EDIT_PIN_CONFIRM:
        return await self._handle_subscriptions_edit_pin_confirm(phone, msg, session, session_service, tenant_id, db)
    return self._t(self.KEY_FALLBACK_ACTIVE_FLOW)


async def _route_subscriptions_lifecycle_flow(self, phone, msg, step, session, session_service, tenant_id, db):
    if step == self.SUBSCRIPTIONS_STEP_CANCEL_CONFIRM:
        return await self._handle_subscriptions_cancel_confirm(phone, msg, session, session_service, tenant_id, db)
    elif step == self.SUBSCRIPTIONS_STEP_REACTIVATE_DURATION:
        return await self._handle_subscriptions_reactivate_duration(phone, msg, session, session_service, tenant_id, db)
    elif step == self.SUBSCRIPTIONS_STEP_REACTIVATE_CUSTOM_DATE:
        return await self._handle_subscriptions_reactivate_custom_date(phone, msg, session, session_service, tenant_id, db)
    elif step == self.SUBSCRIPTIONS_STEP_REACTIVATE_CONFIRM:
        return await self._handle_subscriptions_reactivate_confirm(phone, msg, session, session_service, tenant_id, db)
    elif step == self.SUBSCRIPTIONS_STEP_RENEW_DURATION:
        return await self._handle_subscriptions_renew_duration(phone, msg, session, session_service, tenant_id, db)
    elif step == self.SUBSCRIPTIONS_STEP_RENEW_CUSTOM_DATE:
        return await self._handle_subscriptions_renew_custom_date(phone, msg, session, session_service, tenant_id, db)
    elif step == self.SUBSCRIPTIONS_STEP_RENEW_CONFIRM:
        return await self._handle_subscriptions_renew_confirm(phone, msg, session, session_service, tenant_id, db)
    return self._t(self.KEY_FALLBACK_ACTIVE_FLOW)
