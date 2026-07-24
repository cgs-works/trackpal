"""Validate the complete private Help release contract."""

from __future__ import annotations

from typing import Any

from app.help.compiler import HelpValidationError, validate_artifact

RELEASE_CONTENT_VERSION = "help-client-manual-1"
REQUIRED_TOPIC_IDS = frozenset(
    {
        "tenant-admin.access-control",
        "tenant-admin.activate-access-code-lookup",
        "tenant-admin.code-services",
        "tenant-admin.dashboard",
        "tenant-admin.data-export",
        "tenant-admin.delete-account",
        "tenant-admin.help",
        "tenant-admin.language",
        "tenant-admin.mailbox",
        "tenant-admin.password",
        "tenant-admin.profile",
        "tenant-admin.whatsapp",
        "tenant-admin.catalog",
        "tenant-admin.clients",
        "tenant-admin.first-pro-client",
        "tenant-admin.public-api",
        "tenant-admin.reminders",
        "tenant-admin.subscription-expirations",
        "tenant-admin.subscriptions",
        "tenant-admin.timezone",
        "client.dashboard",
        "client.password",
        "client.profile",
        "client.subscriptions",
        "client.whatsapp",
    }
)
REQUIRED_TOUR_RELEASES = {
    "tenant-admin-starter-1": 7,
    "tenant-admin-pro-1": 7,
    "tenant-admin-pro-upgrade-1": 5,
}


def validate_release_artifact(
    artifact: dict[str, Any], *, allow_target_contract_mismatch: bool = False
) -> None:
    """Validate the artifact required for the first atomic Help release."""

    validate_artifact(
        artifact, allow_target_contract_mismatch=allow_target_contract_mismatch
    )

    if artifact.get("content_version") != RELEASE_CONTENT_VERSION:
        raise HelpValidationError(
            "Unexpected private Help release content version: "
            f"{artifact.get('content_version')!r}"
        )

    for locale in ("en", "es"):
        topics = artifact["topics"][locale]
        topic_ids = {topic.get("id") for topic in topics}
        if topic_ids != REQUIRED_TOPIC_IDS:
            raise HelpValidationError(
                f"Incomplete private Help topic set for {locale}: "
                f"missing={sorted(REQUIRED_TOPIC_IDS - topic_ids)}, "
                f"unexpected={sorted(topic_ids - REQUIRED_TOPIC_IDS)}"
            )

        audiences = {topic.get("audience") for topic in topics}
        if audiences != {"tenant_admin", "client"}:
            raise HelpValidationError(
                f"Private Help release must contain both audiences for {locale}"
            )
        if any(
            topic.get("audience") == "client" and topic.get("tour") for topic in topics
        ):
            raise HelpValidationError(
                "Client Help topics cannot declare orientation tours"
            )

        search_ids = {item.get("id") for item in artifact["search"][locale]}
        if search_ids != topic_ids:
            raise HelpValidationError(
                f"Private Help search index is incomplete for {locale}"
            )

        releases = {
            release.get("release_id"): release
            for release in artifact["tour_releases"][locale]
        }
        if set(releases) != set(REQUIRED_TOUR_RELEASES):
            raise HelpValidationError(
                f"Private Help tour release set is incomplete for {locale}"
            )
        for release_id, expected_steps in REQUIRED_TOUR_RELEASES.items():
            steps = releases[release_id].get("steps", [])
            if len(steps) != expected_steps:
                raise HelpValidationError(
                    f"Help tour release {release_id} must contain "
                    f"{expected_steps} steps"
                )
