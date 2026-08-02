from app.core.i18n import t
from app.core.i18n.catalogs_en_frontend import _CATALOG_EN_FRONTEND
from app.core.i18n.catalogs_es_frontend import _CATALOG_ES_FRONTEND


EXECUTOR_UI_KEYS = [
    "frontend.master.executors.loading",
    "frontend.master.executors.refresh",
    "frontend.master.executors.retry",
    "frontend.master.executors.error_load",
    "frontend.master.executors.health",
    "frontend.master.executors.capacity",
    "frontend.master.executors.last_error",
    "frontend.master.executors.no_error",
    "frontend.master.executors.reverification_required",
    "frontend.master.executors.not_available",
    "frontend.master.executors.capacity_value",
    "frontend.master.executors.transport_http_encrypted",
    "frontend.master.executors.transport_https",
]


EXECUTOR_ERROR_KEYS = [
    "frontend.master.executors.error_insecure_http_confirmation_required",
    "frontend.master.executors.error_requires_verification",
    "frontend.master.executors.error_step_up_rate_limited",
]


def test_executor_operational_ui_keys_are_translated_in_both_catalogs():
    for key in EXECUTOR_UI_KEYS + EXECUTOR_ERROR_KEYS:
        assert _CATALOG_EN_FRONTEND.get(key), f"Missing English key: {key}"
        assert _CATALOG_ES_FRONTEND.get(key), f"Missing Spanish key: {key}"
        params = {"active": 1, "maximum": 2} if key.endswith("capacity_value") else {}
        assert t("en", key, **params) != key
        assert t("es", key, **params) != key
