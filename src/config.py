from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    google_api_key: str
    telegram_bot_token: str = ""
    database_url: str = "sqlite+aiosqlite:///./magikbook.db"
    redis_url: str = ""
    frontend_url: str = "http://localhost:3000"
    secret_key: str = "secret"
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 10080  # 7 days

    gemini_stream_timeout_seconds: int = 45

    # OAuth Configuration
    google_client_id: str = ""
    google_client_secret: str = ""
    google_redirect_uri: str = "https://magikbook.ru/api/auth/google/callback"

    vk_client_id: str = ""
    vk_client_secret: str = ""
    vk_redirect_uri: str = "https://magikbook.ru/api/auth/vk/callback"

    # File Upload Configuration
    upload_dir: str = "./uploads/temp"
    max_file_size: int = 50 * 1024 * 1024  # 50 MB
    file_cleanup_days: int = 7  # Автоочистка файлов старше 7 дней

    # Publishing Configuration
    vk_access_token: str = ""
    vk_group_id: str = ""  # с минусом, например "-123456789"
    telegram_channel_id: str = ""  # @channel_username или числовой ID

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")


settings = Settings()
