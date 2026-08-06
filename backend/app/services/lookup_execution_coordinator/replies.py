"""Localized user-facing messages for terminal mailbox lookups."""

from __future__ import annotations

from app.core.i18n import t

_SERVICE_LABELS: dict[str, str] = {
    "netflix": "Netflix",
    "disney": "Disney+",
    "hbo_max": "HBO Max",
    "prime_video": "Prime Video",
    "spotify": "Spotify",
    "universal_plus": "Universal+",
}

_DEADLINE_ERROR_CODES = {None, "", "lookup_timeout", "timeout"}


def render_lookup_reply(
    locale: str,
    *,
    status: str,
    result_type: str | None,
    result_value: str | None,
    error_code: str | None,
    service_key: str,
) -> str | None:
    """Render the terminal lookup message consumed directly by n8n."""
    service = _SERVICE_LABELS.get(service_key, service_key.replace("_", " ").title())

    if result_type == "code" and result_value:
        return t(
            locale,
            "wa.tenant.codigo.found_code",
            service=service,
            value=result_value,
        )
    if result_type == "url" and result_value:
        return t(
            locale,
            "wa.tenant.codigo.found_url",
            service=service,
            value=result_value,
        )
    if result_type == "not_found" or (
        status == "timeout" and error_code in _DEADLINE_ERROR_CODES
    ):
        return _with_actions(
            locale,
            t(locale, "wa.tenant.codigo.not_found", service=service),
        )
    if result_type == "duplicate_suppressed":
        return _with_actions(locale, t(locale, "wa.tenant.codigo.duplicate"))
    if status == "timeout":
        return _with_actions(locale, t(locale, "wa.tenant.codigo.timeout"))
    if status == "failed" and error_code != "user_cancelled":
        return _with_actions(locale, t(locale, "wa.tenant.codigo.error"))
    return None


def _with_actions(locale: str, message: str) -> str:
    return message + t(locale, "wa.tenant.codigo.result_actions")
