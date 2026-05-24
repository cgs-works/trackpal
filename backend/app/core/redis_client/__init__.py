"""Redis connection manager with active-passive primary/backup pools."""

from .lifespan import close_redis, get_redis, get_redis_manager, init_redis
from .manager import RedisConnectionManager
from .types import FailoverState, RedisUnavailableError, is_redis_infra_error
from .policy import FailoverPolicy

__all__ = [
    "close_redis",
    "FailoverPolicy",
    "FailoverState",
    "get_redis",
    "get_redis_manager",
    "init_redis",
    "is_redis_infra_error",
    "RedisConnectionManager",
    "RedisUnavailableError",
]
