from dataclasses import dataclass, field


@dataclass
class NonceCache:
    """Bounded in-memory replay cache for signed request nonces."""

    ttl_seconds: int
    max_entries: int
    _entries: dict[str, int] = field(default_factory=dict, init=False)

    def __post_init__(self) -> None:
        if self.ttl_seconds <= 0:
            raise ValueError("ttl_seconds must be positive")
        if self.max_entries <= 0:
            raise ValueError("max_entries must be positive")

    def consume(self, nonce: str, now: int) -> bool:
        """Consume a nonce once until its TTL expires."""

        self._purge(now)
        if nonce in self._entries:
            return False
        if len(self._entries) >= self.max_entries:
            return False
        self._entries[nonce] = now + self.ttl_seconds
        return True

    def _purge(self, now: int) -> None:
        expired = [nonce for nonce, expiry in self._entries.items() if expiry <= now]
        for nonce in expired:
            del self._entries[nonce]
