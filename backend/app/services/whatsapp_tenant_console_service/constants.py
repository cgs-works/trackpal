"""Shared flow identifiers and client-specific constants for Tenant Console."""

from __future__ import annotations

# -- i18n key constants --------------------------------------------------

KEY_MAIN_MENU = "wa.tenant.main_menu"
KEY_HELP_TEXT = "wa.tenant.help"
KEY_FALLBACK_NO_FLOW = "wa.tenant.fallback.no_flow"
KEY_FALLBACK_ACTIVE_FLOW = "wa.tenant.fallback.active_flow"

RESET_COMMANDS = {"0", "menu", "menú", "/menu", "cancelar", "salir", "cerrar"}
HELP_COMMANDS = {"5", "ayuda"}

# -- Flow identifiers ----------------------------------------------------

CLIENTS_FLOW = "clients"
CLIENTS_STEP_LIST = "list"
CLIENTS_STEP_SELECT = "select"
CLIENTS_STEP_DETAIL = "detail"
CLIENTS_STEP_DETAIL_ACTION = "detail_action"
CLIENTS_STEP_CREATE_FULL_NAME = "create_full_name"
CLIENTS_STEP_CREATE_PHONE = "create_phone"
CLIENTS_STEP_CREATE_USERNAME = "create_username"
CLIENTS_STEP_CREATE_PASSWORD = "create_password"
CLIENTS_STEP_CREATE_CONFIRM = "create_confirm"
CLIENTS_STEP_EDIT_FIELD = "edit_field"
CLIENTS_STEP_EDIT_VALUE = "edit_value"
CLIENTS_STEP_DEACTIVATE_CONFIRM = "deactivate_confirm"
CLIENTS_STEP_DELETE_CONFIRM = "delete_confirm"
CLIENTS_STEP_BLOCK_LIST = "block_list"
CLIENTS_STEP_BLOCK_UNBLOCK = "block_unblock"

CATALOG_FLOW = "catalog"
CATALOG_STEP_LIST = "list"
CATALOG_STEP_SERVICE_SELECT = "service_select"
CATALOG_STEP_SERVICE_DETAIL = "service_detail"
CATALOG_STEP_SERVICE_ACTION = "service_action"
CATALOG_STEP_EDIT_SERVICE = "edit_service"
CATALOG_STEP_PLAN_SELECT = "plan_select"
CATALOG_STEP_PLAN_DETAIL = "plan_detail"
CATALOG_STEP_PLAN_ACTION = "plan_action"
CATALOG_STEP_EDIT_PLAN = "edit_plan"
CATALOG_STEP_MENU = "menu"
CATALOG_STEP_CREATE_SERVICE_NAME = "create_service_name"
CATALOG_STEP_CREATE_PLAN_NAME = "create_plan_name"
CATALOG_STEP_EMPTY_PLAN_MENU = "empty_plan_menu"
CATALOG_STEP_POST_ACTION = "post_action"
CATALOG_STEP_DELETE_SERVICE_SELECT = "delete_service_select"
CATALOG_STEP_DELETE_SERVICE_CONFIRM = "delete_service_confirm"
CATALOG_STEP_DELETE_PLAN_SELECT = "delete_plan_select"
CATALOG_STEP_DELETE_PLAN_CONFIRM = "delete_plan_confirm"

CATALOG_PAGE_SIZE = 7

PROFILE_FLOW = "profile"
PROFILE_STEP_ACTION = "action"
PROFILE_STEP_EDIT_FIELD = "edit_field"
PROFILE_STEP_EDIT_VALUE = "edit_value"
PROFILE_STEP_CHANGE_PASSWORD_OLD = "change_password_old"
PROFILE_STEP_CHANGE_PASSWORD_NEW = "change_password_new"
PROFILE_STEP_CHANGE_LOCALE_SELECT = "change_locale_select"

SUBSCRIPTIONS_FLOW = "subscriptions"
SUBSCRIPTIONS_STEP_MENU = "menu"
SUBSCRIPTIONS_STEP_FILTER = "filter"
SUBSCRIPTIONS_STEP_LIST = "list"
SUBSCRIPTIONS_STEP_SELECT = "select"
SUBSCRIPTIONS_STEP_DETAIL = "detail"
SUBSCRIPTIONS_STEP_ACTION = "action"
SUBSCRIPTIONS_STEP_CREATE_CLIENT = "create_client"
SUBSCRIPTIONS_STEP_CREATE_SERVICE = "create_service"
SUBSCRIPTIONS_STEP_CREATE_PLAN = "create_plan"
SUBSCRIPTIONS_STEP_CREATE_EMAIL = "create_email"
SUBSCRIPTIONS_STEP_CREATE_PASSWORD = "create_password"
SUBSCRIPTIONS_STEP_CREATE_PASSWORD_CONFIRM = "create_password_confirm"
SUBSCRIPTIONS_STEP_CREATE_PROFILE_OPTION = "create_profile_option"
SUBSCRIPTIONS_STEP_CREATE_PROFILE_NAME = "create_profile_name"
SUBSCRIPTIONS_STEP_CREATE_PIN = "create_pin"
SUBSCRIPTIONS_STEP_CREATE_PIN_CONFIRM = "create_pin_confirm"
SUBSCRIPTIONS_STEP_CREATE_DURATION = "create_duration"
SUBSCRIPTIONS_STEP_CREATE_CUSTOM_DATE = "create_custom_date"
SUBSCRIPTIONS_STEP_CREATE_CONFIRM = "create_confirm"
SUBSCRIPTIONS_STEP_CREATE_DUPLICATE = "create_duplicate"
SUBSCRIPTIONS_STEP_EDIT_FIELD = "edit_field"
SUBSCRIPTIONS_STEP_EDIT_VALUE = "edit_value"
SUBSCRIPTIONS_STEP_EDIT_PASSWORD_CONFIRM = "edit_password_confirm"
SUBSCRIPTIONS_STEP_EDIT_PIN_CONFIRM = "edit_pin_confirm"
SUBSCRIPTIONS_STEP_CANCEL_CONFIRM = "cancel_confirm"
SUBSCRIPTIONS_STEP_REACTIVATE_DURATION = "reactivate_duration"
SUBSCRIPTIONS_STEP_REACTIVATE_CUSTOM_DATE = "reactivate_custom_date"
SUBSCRIPTIONS_STEP_REACTIVATE_CONFIRM = "reactivate_confirm"
SUBSCRIPTIONS_STEP_RENEW_DURATION = "renew_duration"
SUBSCRIPTIONS_STEP_RENEW_CUSTOM_DATE = "renew_custom_date"
SUBSCRIPTIONS_STEP_RENEW_CONFIRM = "renew_confirm"

# -- Client constants ----------------------------------------------------

KEY_CLIENTS_MENU = "wa.tenant.clients.menu"
KEY_CLIENT_NO_CLIENTS = "wa.tenant.clients.no_clients"
KEY_CLIENT_SELECT_PROMPT = "wa.tenant.clients.select_prompt"
KEY_CLIENT_DETAIL_ACTIVE_ACTIONS = "wa.tenant.clients.detail.active_actions"
KEY_CLIENT_DETAIL_INACTIVE_ACTIONS = "wa.tenant.clients.detail.inactive_actions"
KEY_CLIENT_CREATE_PROMPT_FULL_NAME = "wa.tenant.clients.create.full_name"
KEY_CLIENT_CREATE_PROMPT_PHONE = "wa.tenant.clients.create.phone"
KEY_CLIENT_CREATE_PROMPT_USERNAME = "wa.tenant.clients.create.username"
KEY_CLIENT_CREATE_PROMPT_PASSWORD = "wa.tenant.clients.create.password"
KEY_CLIENT_CREATE_CONFIRM_TEMPLATE = "wa.tenant.clients.create.confirm"
KEY_CLIENT_CREATE_SUCCESS = "wa.tenant.clients.create.success"
KEY_CLIENT_CREATE_ERROR_PHONE = "wa.tenant.clients.create.error_phone"
KEY_CLIENT_EDIT_FIELD_PROMPT = "wa.tenant.clients.edit.field_prompt"

CLIENT_EDIT_FIELD_MAP = {
    "1": "full_name",
    "2": "phone",
    "3": "local_username",
}

CLIENT_EDIT_PROMPTS = {
    "full_name": ("✏️ *Editar Cliente*\n\n¿Cuál es el *nuevo nombre completo*?"),
    "phone": ("✏️ *Editar Cliente*\n\n¿Cuál es el *nuevo teléfono*?"),
    "local_username": (
        "✏️ *Editar Cliente*\n\n¿Cuál es el *nuevo nombre de usuario local*?"
    ),
}

KEY_CLIENT_EDIT_ERROR_INVALID_FIELD = "wa.tenant.clients.edit.invalid_field"
KEY_CLIENT_DEACTIVATE_CONFIRM_TEMPLATE = "wa.tenant.clients.deactivate.confirm"
KEY_CLIENT_DELETE_CONFIRM_TEMPLATE = "wa.tenant.clients.delete.confirm"
KEY_CLIENT_CANT_DELETE_ACTIVE = "wa.tenant.clients.cant_delete_active"
KEY_CLIENT_DEACTIVATE_SUCCESS = "wa.tenant.clients.deactivate.success"
KEY_CLIENT_REACTIVATE_SUCCESS = "wa.tenant.clients.reactivate.success"
KEY_CLIENT_DELETE_SUCCESS = "wa.tenant.clients.delete.success"
KEY_CLIENT_EDIT_SUCCESS = "wa.tenant.clients.edit.success"
KEY_CLIENT_CONFIRM_REPROMPT = "wa.tenant.clients.confirm_reprompt"
KEY_CLIENT_INVALID_SELECTION = "wa.tenant.clients.invalid_selection"
KEY_CLIENT_NAME_REQUIRED = "wa.tenant.clients.name_required"
KEY_CLIENT_USERNAME_REQUIRED = "wa.tenant.clients.username_required"
KEY_CLIENT_SHORT_PASSWORD = "wa.tenant.clients.short_password"
KEY_CLIENT_BLOCK_LIST_EMPTY = "wa.tenant.clients.blocks.list_empty"
KEY_CLIENT_BLOCK_LIST_HEADER = "wa.tenant.clients.blocks.list_header"
KEY_CLIENT_BLOCK_UNBLOCK_PROMPT = "wa.tenant.clients.blocks.unblock_prompt"
KEY_CLIENT_BLOCK_UNBLOCK_SUCCESS = "wa.tenant.clients.blocks.unblock_success"
KEY_CLIENT_BLOCK_INVALID_SELECTION = "wa.tenant.clients.blocks.invalid_selection"
CLIENT_SKIP_WORDS = {"—", "skip", "ninguno", "none", "-"}

# -- Catalog constants ---------------------------------------------------

KEY_CATALOG_MENU = "wa.tenant.catalog.menu"
KEY_CATALOG_NO_SERVICES = "wa.tenant.catalog.no_services"
KEY_CATALOG_SERVICE_PROMPT = "wa.tenant.catalog.service_prompt"
KEY_CATALOG_SERVICE_ACTIONS = "wa.tenant.catalog.service_actions"
KEY_CATALOG_SERVICE_EDIT_PROMPT = "wa.tenant.catalog.service_edit_prompt"
KEY_CATALOG_SERVICE_EDIT_SUCCESS = "wa.tenant.catalog.service_edit_success"
KEY_CATALOG_PLAN_ACTIONS = "wa.tenant.catalog.plan_actions"
KEY_CATALOG_NO_PLANS = "wa.tenant.catalog.no_plans"
KEY_CATALOG_PLAN_PROMPT = "wa.tenant.catalog.plan_prompt"
KEY_CATALOG_PLAN_EDIT_PROMPT = "wa.tenant.catalog.plan_edit_prompt"
KEY_CATALOG_PLAN_EDIT_SUCCESS = "wa.tenant.catalog.plan_edit_success"
KEY_CATALOG_INVALID_SELECTION = "wa.tenant.catalog.invalid_selection"
KEY_CATALOG_NAME_REQUIRED = "wa.tenant.catalog.name_required"
KEY_CATALOG_EMPTY_MENU = "wa.tenant.catalog.empty_menu"
KEY_CATALOG_CREATE_SERVICE_PROMPT = "wa.tenant.catalog.create_service_prompt"
KEY_CATALOG_CREATE_SERVICE_SUCCESS = "wa.tenant.catalog.create_service_success"
KEY_CATALOG_CREATE_PLAN_PROMPT = "wa.tenant.catalog.create_plan_prompt"
KEY_CATALOG_CREATE_PLAN_SUCCESS = "wa.tenant.catalog.create_plan_success"
KEY_CATALOG_EMPTY_PLANS_MENU = "wa.tenant.catalog.empty_plans_menu"
KEY_CATALOG_NO_PLANS_FOR_DELETE = "wa.tenant.catalog.no_plans_for_delete"
KEY_CATALOG_POST_SUCCESS_PROMPT = "wa.tenant.catalog.post_success_prompt"
KEY_CATALOG_POST_SUCCESS_INVALID = "wa.tenant.catalog.post_success_invalid"

# -- Profile constants ---------------------------------------------------

KEY_PROFILE_MENU = "wa.tenant.profile.menu"
KEY_PROFILE_EDIT_FIELD_PROMPT = "wa.tenant.profile.edit_field_prompt"

PROFILE_EDIT_FIELD_MAP = {
    "1": "full_name",
    "2": "email",
    "3": "phone",
}

PROFILE_EDIT_PROMPTS = {
    "full_name": ("✏️ *Editar Perfil*\n\n¿Cuál es el *nuevo nombre completo*?"),
    "email": ("✏️ *Editar Perfil*\n\n¿Cuál es el *nuevo email*?"),
    "phone": ("✏️ *Editar Perfil*\n\n¿Cuál es el *nuevo teléfono*?"),
}

KEY_PROFILE_EDIT_ERROR_INVALID_FIELD = "wa.tenant.profile.edit_invalid_field"
KEY_PROFILE_EDIT_SUCCESS = "wa.tenant.profile.edit_success"
KEY_PROFILE_CHANGE_PASSWORD_PROMPT_OLD = "wa.tenant.profile.change_password_old"
KEY_PROFILE_CHANGE_PASSWORD_PROMPT_NEW = "wa.tenant.profile.change_password_new"
KEY_PROFILE_CHANGE_PASSWORD_ERROR_OLD = "wa.tenant.profile.change_password_error_old"
KEY_PROFILE_CHANGE_PASSWORD_SUCCESS = "wa.tenant.profile.change_password_success"

KEY_PROFILE_LOCALE_SELECT = "wa.tenant.profile.locale_select"

# -- Codigo flow constants ------------------------------------------------

CODIGO_FLOW = "codigo"
CODIGO_STEP_SERVICE = "service"
CODIGO_STEP_EMAIL = "email"
CODIGO_STEP_EMAIL_CONFIRM = "email_confirm"
CODIGO_STEP_AWAITING_RESULT = "awaiting_result"

KEY_CODIGO_MENU = "wa.tenant.codigo.menu"
KEY_CODIGO_SERVICE_PROMPT = "wa.tenant.codigo.service_prompt"
KEY_CODIGO_EMAIL_PROMPT = "wa.tenant.codigo.email_prompt"
KEY_CODIGO_EMAIL_CONFIRM_PROMPT = "wa.tenant.codigo.email_confirm_prompt"
KEY_CODIGO_INVALID_EMAIL_CONFIRM_OPTION = (
    "wa.tenant.codigo.invalid_email_confirm_option"
)
KEY_CODIGO_BUSCANDO = "wa.tenant.codigo.buscando"
KEY_CODIGO_FOUND_CODE = "wa.tenant.codigo.found_code"
KEY_CODIGO_FOUND_URL = "wa.tenant.codigo.found_url"
KEY_CODIGO_NOT_FOUND = "wa.tenant.codigo.not_found"
KEY_CODIGO_DUPLICATE = "wa.tenant.codigo.duplicate"
KEY_CODIGO_ERROR = "wa.tenant.codigo.error"
KEY_CODIGO_TIMEOUT = "wa.tenant.codigo.timeout"
KEY_CODIGO_INVALID_SERVICE = "wa.tenant.codigo.invalid_service"
KEY_CODIGO_NO_MAILBOX = "wa.tenant.codigo.no_mailbox"
KEY_CODIGO_NO_CODE_SERVICES_TENANT = "wa.tenant.codigo.no_code_services_tenant"
KEY_CODIGO_NO_CODE_SERVICES_CLIENT = "wa.tenant.codigo.no_code_services_client"

# Global service keys available for code lookup
# Alphabetical order by visible label (Disney+, HBO Max, Netflix, Prime Video, Spotify, Universal+)
STREAMING_SERVICE_KEYS: list[str] = [
    "disney",  # 1️⃣ Disney+
    "hbo_max",  # 2️⃣ HBO Max
    "netflix",  # 3️⃣ Netflix
    "prime_video",  # 4️⃣ Prime Video
    "spotify",  # 5️⃣ Spotify
    "universal_plus",  # 6️⃣ Universal+
]
