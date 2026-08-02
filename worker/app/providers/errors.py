"""Provider error taxonomy used by the lookup pipeline."""


class ProviderFetchError(Exception):
    """Base class for failures while fetching messages."""


class TransientProviderError(ProviderFetchError):
    """A network, timeout, rate-limit, or other retryable failure."""


class NonTransientProviderError(ProviderFetchError):
    """A provider configuration or authentication failure."""

    def __init__(self, message: str, error_code: str = "auth_failed") -> None:
        super().__init__(message)
        self.error_code = error_code


__all__ = [
    "NonTransientProviderError",
    "ProviderFetchError",
    "TransientProviderError",
]
