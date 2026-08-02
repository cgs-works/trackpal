from uuid import UUID

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class ExecutorSettings(BaseSettings):
    """Runtime configuration for a lookup executor."""

    model_config = SettingsConfigDict(env_prefix="TRACKPAL_")

    executor_id: UUID
    executor_secret: str
    max_concurrency: int = Field(default=1, gt=0)
