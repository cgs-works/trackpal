"""Provider-specific email fetch adapters.

Each adapter fetches recent emails from a mailbox using Gmail app-password
authentication. The stub adapter is used for integration tests.

Error taxonomy:
- ``TransientProviderError`` — network/rate-limit/timeout (retryable)
- ``NonTransientProviderError`` — auth/permission (fatal)
"""

from __future__ import annotations

from app.models.tenant_mailbox import TenantMailbox
from app.services.mail_lookup_worker.providers._gmail_app_password import (
    fetch_gmail_app_password_emails,
)
from app.services.mail_lookup_worker.providers._types import (
    EmailMessage,
    NonTransientProviderError,
    ProviderFetchError,
    TransientProviderError,
)


class StubProvider:
    """Returns deterministic mock emails for testing the pipeline.

    Callers inject this at test time via the module-level
    ``active_provider`` override or monkey-patching.
    """

    def __init__(self, emails: list[EmailMessage] | None = None) -> None:
        self._emails = emails

    async def fetch_recent(
        self,
        mailbox: TenantMailbox,
        window_minutes: int,
    ) -> list[EmailMessage]:
        if self._emails is not None:
            return self._emails
        return []


#: Module-level override for testing — set to a ``StubProvider`` instance.
active_provider: StubProvider | None = None


async def fetch_recent_emails(
    mailbox: TenantMailbox,
    window_minutes: int,
) -> list[EmailMessage]:
    """Dispatch to the Gmail app-password adapter.

    If ``active_provider`` is set (testing), delegates to it instead.
    Content-level ``target_email`` filtering (subject/body) is handled
    in ``_helpers._filter_emails_by_target_email`` after fetch.
    """
    if active_provider is not None:
        return await active_provider.fetch_recent(mailbox, window_minutes)
    return await fetch_gmail_app_password_emails(mailbox, window_minutes)


__all__ = [
    "EmailMessage",
    "ProviderFetchError",
    "TransientProviderError",
    "NonTransientProviderError",
    "StubProvider",
    "active_provider",
    "fetch_recent_emails",
]
