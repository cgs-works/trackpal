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
    master_name: str = "Master TrackPal"
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
    whatsapp_session_ttl_minutes: int = 5
    whatsapp_auth_fail_threshold: int = 5
    whatsapp_auth_lock_minutes: int = 5
    whatsapp_auth_fail_window_minutes: int = 15
    master_whatsapp_instance: str = ""
    data_encryption_key: str = ""

    # Google OAuth
    google_oauth_client_id: str = ""
    google_oauth_client_secret: str = ""
    google_oauth_redirect_uri: str = (
        "http://localhost:8000/api/v1/tenant/mailbox/oauth/google/callback"
    )

    # R2 / S3 for debug uploads
    r2_access_key_id: str = ""
    r2_secret_access_key: str = ""
    r2_bucket_name: str = "trackpal-debug"
    r2_endpoint_url: str = ""
    r2_public_url: str = ""

    # Export storage — dedicated private R2 for Tenant Data Export
    # Must NEVER fall back to or share config with the public diagnostic R2 bucket.
    export_r2_access_key_id: str = ""
    export_r2_secret_access_key: str = ""
    export_r2_bucket_name: str = ""
    export_r2_endpoint_url: str = ""
    export_signed_url_ttl_seconds: int = 900

    @property
    def is_export_storage_configured(self) -> bool:
        """True when all required export-storage fields are non-empty."""
        return bool(
            self.export_r2_access_key_id
            and self.export_r2_secret_access_key
            and self.export_r2_bucket_name
            and self.export_r2_endpoint_url
        )

    # Mailbox lookup defaults
    mailbox_lookup_timeout_seconds: int = 20
    mailbox_lookup_window_minutes: int = 5
    mailbox_lookup_job_ttl_minutes: int = 5
    mailbox_delivery_log_retention_days: int = 7

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")


settings = Settings()  # pyright: ignore[reportCallIssue]
