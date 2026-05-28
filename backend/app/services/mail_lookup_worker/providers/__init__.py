"""Provider-specific email fetch adapters.

Each adapter fetches recent emails from a mailbox using its configured
authentication method (OAuth2 for Google/Microsoft, app-password for
IMAP).  The stub adapter is used for integration tests.

Error taxonomy:
- ``TransientProviderError`` — network/rate-limit/timeout (retryable)
- ``NonTransientProviderError`` — auth/revoked/permission (fatal)
"""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.tenant_mailbox import TenantMailbox
from app.services.mail_lookup_worker.providers._google import fetch_google_emails
from app.services.mail_lookup_worker.providers._imap import fetch_imap_emails
from app.services.mail_lookup_worker.providers._microsoft import fetch_microsoft_emails
from app.services.mail_lookup_worker.providers._types import (
    EmailMessage,
    NonTransientProviderError,
    ProviderFetchError,
    RevokedMailboxError,
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
        target_email: str | None = None,
        db: AsyncSession | None = None,
    ) -> list[EmailMessage]:
        if self._emails is not None:
            return self._emails
        return []


#: Module-level override for testing — set to a ``StubProvider`` instance.
active_provider: StubProvider | None = None


async def fetch_recent_emails(
    mailbox: TenantMailbox,
    window_minutes: int,
    target_email: str | None = None,
    db: AsyncSession | None = None,
) -> list[EmailMessage]:
    """Dispatch to the appropriate provider based on mailbox config.

    If ``active_provider`` is set (testing), delegates to it instead.
    Content-level ``target_email`` filtering (subject/body) is handled
    in ``_helpers._filter_emails_by_target_email`` after fetch.
    ``db`` is required for OAuth providers to handle token refresh on 401.
    """
    if active_provider is not None:
        emails = await active_provider.fetch_recent(
            mailbox, window_minutes, target_email=target_email, db=db
        )
    elif mailbox.auth_method == "oauth":
        if mailbox.provider == "google":
            emails = await fetch_google_emails(mailbox, window_minutes, db=db)
        elif mailbox.provider == "microsoft":
            emails = await fetch_microsoft_emails(mailbox, window_minutes, db=db)
        else:
            raise NonTransientProviderError(
                f"Unsupported OAuth provider: {mailbox.provider}",
                error_code="provider_config_error",
            )
    elif mailbox.auth_method == "imap_app_password":
        emails = await fetch_imap_emails(mailbox, window_minutes)
    else:
        raise NonTransientProviderError(
            f"Unsupported provider/auth: {mailbox.provider}/{mailbox.auth_method}",
            error_code="provider_config_error",
        )

    # Content-level semantic filtering (subject/body/recipients) is handled by
    # ``_helpers._filter_emails_by_target_email`` after fetch, so the extractor
    # sees all candidates and content matching works for forwarded/aliased mail.
    return emails


__all__ = [
    "EmailMessage",
    "ProviderFetchError",
    "RevokedMailboxError",
    "TransientProviderError",
    "NonTransientProviderError",
    "StubProvider",
    "active_provider",
    "fetch_recent_emails",
]
