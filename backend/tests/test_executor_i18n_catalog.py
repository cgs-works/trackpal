from app.core.i18n.catalogs_en_frontend import _CATALOG_EN_FRONTEND
from app.core.i18n.catalogs_es_frontend import _CATALOG_ES_FRONTEND


EXECUTOR_COMPONENT_KEYS = {
    "frontend.master.executors.error_create",
    "frontend.master.executors.error_capacity_exceeds_advertised",
    "frontend.master.executors.error_verification_failed",
    "frontend.master.executors.error_enable",
    "frontend.master.executors.wizard_title",
    "frontend.master.executors.wizard_description",
    "frontend.master.executors.name",
    "frontend.master.executors.provider",
    "frontend.master.executors.max_concurrency",
    "frontend.master.executors.cancel",
    "frontend.master.executors.next",
    "frontend.master.executors.base_url",
    "frontend.master.executors.transport_mode",
    "frontend.master.executors.transport_https",
    "frontend.master.executors.transport_http_encrypted",
    "frontend.master.executors.verify",
    "frontend.master.executors.connection_healthy",
    "frontend.master.executors.protocol_version",
    "frontend.master.executors.runtime_version",
    "frontend.master.executors.advertised_capacity",
    "frontend.master.executors.advertised_capacity_value",
    "frontend.master.executors.enable",
    "frontend.master.executors.step_identity",
    "frontend.master.executors.step_credentials",
    "frontend.master.executors.step_connection",
    "frontend.master.executors.step_activation",
    "frontend.master.executors.hosting_details",
    "frontend.master.executors.hosting_email",
    "frontend.master.executors.hosting_password",
    "frontend.master.executors.dashboard_url",
    "frontend.master.executors.copy_error",
    "frontend.master.executors.one_time_secret_title",
    "frontend.master.executors.one_time_secret_description",
    "frontend.master.executors.executor_id",
    "frontend.master.executors.copy_executor_id",
    "frontend.master.executors.executor_id_copied",
    "frontend.master.executors.one_time_secret",
    "frontend.master.executors.copy_secret",
    "frontend.master.executors.secret_copied",
    "frontend.master.executors.secret_dismiss_warning",
    "frontend.master.executors.credentials_continue",
}


def test_executor_dialog_keys_exist_in_english_and_spanish_catalogs():
    assert EXECUTOR_COMPONENT_KEYS <= _CATALOG_EN_FRONTEND.keys()
    assert EXECUTOR_COMPONENT_KEYS <= _CATALOG_ES_FRONTEND.keys()
