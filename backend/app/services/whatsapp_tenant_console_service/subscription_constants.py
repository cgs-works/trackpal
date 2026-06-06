"""Subscription-specific constants for the Tenant Console."""

from __future__ import annotations

# -- Subscription message keys -------------------------------------------

KEY_SUBSCRIPTIONS_MENU = "wa.tenant.subscriptions.menu"
KEY_SUBSCRIPTIONS_FILTER_PROMPT = "wa.tenant.subscriptions.filter_prompt"
KEY_SUBSCRIPTIONS_NO_RESULTS = "wa.tenant.subscriptions.no_results"
KEY_SUBSCRIPTIONS_SELECT_PROMPT = "wa.tenant.subscriptions.select_prompt"
KEY_SUBSCRIPTION_DETAIL_ACTIONS = "wa.tenant.subscriptions.detail.actions"
KEY_SUBSCRIPTION_DETAIL_ACTIONS_ACTIVE = "wa.tenant.subscriptions.detail.actions_active"

KEY_SUBSCRIPTIONS_CREATE_CLIENT_PROMPT = "wa.tenant.subscriptions.create.client_prompt"
KEY_SUBSCRIPTIONS_CREATE_SERVICE_PROMPT = "wa.tenant.subscriptions.create.service_prompt"
KEY_SUBSCRIPTIONS_CREATE_PLAN_PROMPT = "wa.tenant.subscriptions.create.plan_prompt"
KEY_SUBSCRIPTIONS_CREATE_EMAIL_PROMPT = "wa.tenant.subscriptions.create.email_prompt"
KEY_SUBSCRIPTIONS_CREATE_PASSWORD_PROMPT = "wa.tenant.subscriptions.create.password_prompt"
KEY_SUBSCRIPTIONS_CREATE_PASSWORD_CONFIRM_PROMPT = "wa.tenant.subscriptions.create.password_confirm"
KEY_SUBSCRIPTIONS_CREATE_PASSWORD_MISMATCH = "wa.tenant.subscriptions.create.password_mismatch"
KEY_SUBSCRIPTIONS_CREATE_PROFILE_NAME_PROMPT = "wa.tenant.subscriptions.create.profile_name"
KEY_SUBSCRIPTIONS_CREATE_PROFILE_OPTION_PROMPT = "wa.tenant.subscriptions.create.profile_option"
KEY_SUBSCRIPTIONS_CREATE_PIN_PROMPT = "wa.tenant.subscriptions.create.pin_prompt"
KEY_SUBSCRIPTIONS_CREATE_PIN_CONFIRM_PROMPT = "wa.tenant.subscriptions.create.pin_confirm"
KEY_SUBSCRIPTIONS_CREATE_PIN_MISMATCH = "wa.tenant.subscriptions.create.pin_mismatch"
KEY_SUBSCRIPTIONS_CREATE_PIN_REQUIRES_PROFILE = "wa.tenant.subscriptions.create.pin_requires_profile"
KEY_SUBSCRIPTIONS_DURATION_PROMPT = "wa.tenant.subscriptions.duration_prompt"
KEY_SUBSCRIPTIONS_CUSTOM_DATE_PROMPT = "wa.tenant.subscriptions.custom_date_prompt"
KEY_SUBSCRIPTIONS_CREATE_CONFIRM_TEMPLATE = "wa.tenant.subscriptions.create.confirm"
KEY_SUBSCRIPTIONS_CREATE_DUPLICATE_NOTICE = "wa.tenant.subscriptions.create.duplicate_notice"
KEY_SUBSCRIPTIONS_CREATE_SUCCESS = "wa.tenant.subscriptions.create.success"

KEY_SUBSCRIPTIONS_EDIT_FIELD_PROMPT = "wa.tenant.subscriptions.edit.field_prompt"
KEY_SUBSCRIPTIONS_EDIT_ERROR_INVALID_FIELD = "wa.tenant.subscriptions.edit.invalid_field"
KEY_SUBSCRIPTIONS_EDIT_SUCCESS = "wa.tenant.subscriptions.edit.success"
KEY_SUBSCRIPTIONS_EDIT_PASSWORD_CONFIRM_PROMPT = "wa.tenant.subscriptions.edit.password_confirm"
KEY_SUBSCRIPTIONS_EDIT_PIN_CONFIRM_PROMPT = "wa.tenant.subscriptions.edit.pin_confirm"
KEY_SUBSCRIPTIONS_EDIT_MISMATCH = "wa.tenant.subscriptions.edit.mismatch"

KEY_SUBSCRIPTIONS_CANCEL_CONFIRM_TEMPLATE = "wa.tenant.subscriptions.cancel.confirm"
KEY_SUBSCRIPTIONS_CANCEL_SUCCESS = "wa.tenant.subscriptions.cancel.success"

KEY_SUBSCRIPTIONS_REACTIVATE_DURATION_PROMPT = "wa.tenant.subscriptions.reactivate.duration_prompt"
KEY_SUBSCRIPTIONS_REACTIVATE_CUSTOM_DATE_PROMPT = "wa.tenant.subscriptions.reactivate.custom_date"
KEY_SUBSCRIPTIONS_REACTIVATE_CONFIRM_TEMPLATE = "wa.tenant.subscriptions.reactivate.confirm"
KEY_SUBSCRIPTIONS_REACTIVATE_SUCCESS = "wa.tenant.subscriptions.reactivate.success"

KEY_SUBSCRIPTIONS_RENEW_DURATION_PROMPT = "wa.tenant.subscriptions.renew.duration_prompt"
KEY_SUBSCRIPTIONS_RENEW_CUSTOM_DATE_PROMPT = "wa.tenant.subscriptions.renew.custom_date"
KEY_SUBSCRIPTIONS_RENEW_CONFIRM_TEMPLATE = "wa.tenant.subscriptions.renew.confirm"
KEY_SUBSCRIPTIONS_RENEW_SUCCESS = "wa.tenant.subscriptions.renew.success"

KEY_SUBSCRIPTIONS_INVALID_SELECTION = "wa.tenant.subscriptions.invalid_selection"
KEY_SUBSCRIPTIONS_CONFIRM_REPROMPT = "wa.tenant.subscriptions.confirm_reprompt"
KEY_SUBSCRIPTIONS_EMAIL_REQUIRED = "wa.tenant.subscriptions.email_required"
KEY_SUBSCRIPTIONS_CLIENT_REQUIRED = "wa.tenant.subscriptions.client_required"

SUBSCRIPTIONS_SKIP_WORDS = {"—", "skip", "ninguno", "none", "-"}

SUBSCRIPTIONS_DURATION_MAP = {
    "1": "1_month",
    "2": "3_months",
    "3": "6_months",
    "4": "9_months",
    "5": "1_year",
    "6": "custom",
}

SUBSCRIPTIONS_EDIT_FIELD_MAP = {
    "1": "client",
    "2": "service",
    "3": "plan",
    "4": "streaming_email",
    "5": "streaming_password",
    "6": "profile_name",
    "7": "profile_pin",
}

SUBSCRIPTIONS_EDIT_PROMPT_KEYS = {
    "streaming_email": "wa.tenant.subscriptions.edit.prompt.streaming_email",
    "streaming_password": "wa.tenant.subscriptions.edit.prompt.streaming_password",
    "profile_name": "wa.tenant.subscriptions.edit.prompt.profile_name",
    "profile_pin": "wa.tenant.subscriptions.edit.prompt.profile_pin",
}
