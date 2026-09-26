from functools import lru_cache
from typing import List

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    DATABASE_URL: str

    SECRET_KEY: str
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 15
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    JWT_ALGORITHM: str = "HS256"

    ENVIRONMENT: str = "development"
    COOKIE_SECURE: bool = False
    COOKIE_DOMAIN: str = ""
    COOKIE_SAMESITE: str = "lax"

    CORS_ORIGINS: str = "http://localhost:5173"

    AI_PROVIDER: str = "groq"
    AI_PROVIDER_FALLBACK: str = "gemini"

    GROQ_API_KEY: str = ""
    GROQ_MODEL: str = "openai/gpt-oss-120b"
    GROQ_TIMEOUT_SECONDS: int = 60
    GROQ_MAX_RETRIES: int = 2

    GEMINI_API_KEY: str = ""
    GEMINI_MODEL: str = "gemini-3.5-flash-lite"
    GEMINI_TIMEOUT_SECONDS: int = 60
    GEMINI_MAX_RETRIES: int = 2

    MAX_UPLOAD_MB: int = 25

    RATE_LIMIT_CALLS: int = 240
    RATE_LIMIT_WINDOW_SECONDS: int = 60
    MAX_REQUEST_BYTES: int = 40 * 1024 * 1024

    @property
    def cors_origin_list(self) -> List[str]:
        return [o.strip() for o in self.CORS_ORIGINS.split(",") if o.strip()]

    @property
    def is_production(self) -> bool:
        return self.ENVIRONMENT.lower() == "production"


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
