from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    database_url: str
    secret_key: str
    n8n_api_key: str
    cors_origins: str = "http://localhost:5173"
    evolution_api_url: str = ""
    evolution_api_key: str = ""
    access_token_expire_minutes: int = 30
    refresh_token_expire_days: int = 7
    master_username: str = "master"
    master_password: str = "changeme"
    master_name: str = "Master Trackpal"
    master_phone: str = "+1234567890"
    redis_url: str = ""
    redis_primary_url: str = ""
    redis_backup_url: str = ""
    redis_pool_size: int = 20
    redis_socket_timeout_seconds: float = 5.0
    redis_connect_timeout_seconds: float = 5.0
    redis_health_check_interval_seconds: float = 30.0
    redis_failover_failure_threshold: int = 3
    redis_breaker_open_seconds: int = 30
    whatsapp_session_ttl_minutes: int = 15

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")


settings = Settings()
