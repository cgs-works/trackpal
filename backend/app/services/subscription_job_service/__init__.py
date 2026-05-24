"""Background job service for subscription lifecycle management.

Called by n8n via the protected job endpoint.
"""

from app.services.subscription_job_service.cleanup import (
    run_cleanup,
    _ensure_aware,
)
from app.services.subscription_job_service.reminder_payloads import (
    generate_reminder_payloads,
    _is_reminder_time_ok,
    _resolve_recipients,
    _render_reminder_message,
)
from app.services.subscription_job_service.reminder_log import (
    mark_reminder_sent,
    mark_reminder_failed,
    run_reminders_stub,
)


class SubscriptionJobService:
    """Background job service for subscription lifecycle management.

    Called by n8n via the protected job endpoint.  All operations use
    UTC as the default timezone; per-tenant timezone from
    ``subscription_reminder_settings`` is supported where available.
    """

    run_cleanup = staticmethod(run_cleanup)
    _ensure_aware = staticmethod(_ensure_aware)
    generate_reminder_payloads = staticmethod(generate_reminder_payloads)
    _is_reminder_time_ok = staticmethod(_is_reminder_time_ok)
    _resolve_recipients = staticmethod(_resolve_recipients)
    _render_reminder_message = staticmethod(_render_reminder_message)
    mark_reminder_sent = staticmethod(mark_reminder_sent)
    mark_reminder_failed = staticmethod(mark_reminder_failed)
    run_reminders_stub = staticmethod(run_reminders_stub)
