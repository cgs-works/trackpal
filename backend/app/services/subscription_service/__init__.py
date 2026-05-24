"""Subscription management — CRUD, lifecycle, reminders."""

from app.services.subscription_service.constants import DURATION_MAP
from app.services.subscription_service.helpers import (
    calculate_expiration,
    commit_change,
    create_event,
)
from app.services.subscription_service.validation import validate_ids
from app.services.subscription_service.queries import (
    get_subscription,
    reveal_credentials,
    list_subscriptions,
    list_subscription_events,
)
from app.services.subscription_service.mutations import (
    create_subscription,
    cancel_subscription,
    reactivate_subscription,
    renew_subscription,
)
from app.services.subscription_service.updater import update_subscription
from app.services.subscription_service.reminder_settings import (
    get_reminder_settings,
    update_reminder_settings,
)


class SubscriptionService:
    """Subscription management — delegates to focused modules."""

    calculate_expiration = staticmethod(calculate_expiration)
    validate_ids = staticmethod(validate_ids)
    _commit_change = staticmethod(commit_change)
    _create_event = staticmethod(create_event)
    get_subscription = staticmethod(get_subscription)
    reveal_credentials = staticmethod(reveal_credentials)
    list_subscriptions = staticmethod(list_subscriptions)
    list_subscription_events = staticmethod(list_subscription_events)
    create_subscription = staticmethod(create_subscription)
    update_subscription = staticmethod(update_subscription)
    cancel_subscription = staticmethod(cancel_subscription)
    reactivate_subscription = staticmethod(reactivate_subscription)
    renew_subscription = staticmethod(renew_subscription)
    get_reminder_settings = staticmethod(get_reminder_settings)
    update_reminder_settings = staticmethod(update_reminder_settings)


__all__ = ["SubscriptionService", "DURATION_MAP"]
