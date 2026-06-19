from typing import Optional

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings. Use ENVIRONMENT=production for secure cookies by default."""

    google_api_key: str = ""
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
    google_redirect_uri: str = "http://localhost:8000/api/auth/google/callback"

    vk_client_id: str = ""
    vk_client_secret: str = ""
    vk_redirect_uri: str = "http://localhost:8000/api/auth/vk/callback"

    # File Upload Configuration
    upload_dir: str = "./uploads/temp"
    max_file_size: int = 50 * 1024 * 1024  # 50 MB
    file_cleanup_days: int = 7  # Автоочистка файлов старше 7 дней

    # Publishing Configuration
    vk_access_token: str = ""
    # Сервисный ключ приложения (ограниченный scope). Постинг wall+фото/видео использует vk_access_token.
    vk_service_access_token: str = ""
    vk_group_id: str = ""  # с минусом, например "-123456789"
    telegram_channel_id: str = ""  # @channel_username или числовой ID

    # Environment ("production" enables Secure cookies unless COOKIE_SECURE overrides)
    environment: str = "development"

    # If set, overrides auto secure cookies (True/False). None = secure only in production.
    cookie_secure: Optional[bool] = Field(default=None)

    # Daily prompt auto-generation via Gemini (arq cron 00:00 UTC).
    # Set to true in .env to re-enable. Default: disabled.
    daily_prompt_enabled: bool = Field(default=False)

    # SMTP (email OTP) — на многих VPS исходящий SMTP (465/587) заблокирован
    smtp_host: str = "smtp.yandex.ru"
    smtp_port: int = 465
    smtp_user: str = ""
    smtp_password: str = ""
    smtp_from: str = "noreply@example.com"
    # Если задан — отправка OTP через Resend HTTPS API (порт 443). Иначе при SMTP_HOST=smtp.resend.com
    # используется SMTP_PASSWORD как API key и тот же API.
    resend_api_key: str = ""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    def cookie_secure_effective(self) -> bool:
        """HttpOnly session cookies: Secure flag for HTTPS production."""
        if self.cookie_secure is not None:
            return self.cookie_secure
        return self.environment.lower() == "production"


settings = Settings()
