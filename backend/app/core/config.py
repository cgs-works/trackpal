from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    database_url: str
    secret_key: str
    n8n_api_key: str
    cors_origins: str = "http://localhost:5173"
    evolution_api_url: str = "https://rs-evoapi.wilfredocamacho.dev"
    evolution_api_key: str = ""
    access_token_expire_minutes: int = 30
    refresh_token_expire_days: int = 7
    master_username: str = "master"
    master_password: str = "changeme"
    master_name: str = "Master Trackpal"
    master_phone: str = "+1234567890"

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")


settings = Settings()
