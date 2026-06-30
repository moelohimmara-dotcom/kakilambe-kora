from pydantic_settings import BaseSettings
from typing import List, Optional


class Settings(BaseSettings):
    # ── App ─────────────────────────────────────────────────────────────────
    DEBUG: bool = False
    # Comma-separated string to avoid pydantic-settings List[str] parsing issues
    ALLOWED_ORIGINS: str = "http://localhost:3000,https://kakilambe.com"

    @property
    def allowed_origins_list(self) -> List[str]:
        return [o.strip() for o in self.ALLOWED_ORIGINS.split(",") if o.strip()]

    # ── LLM Providers ───────────────────────────────────────────────────────
    GROQ_API_KEY: str = ""
    GEMINI_API_KEY: str = ""
    CEREBRAS_API_KEY: str = ""
    OPENROUTER_API_KEY: str = ""

    LLM_PROVIDER_ORDER: str = "groq,gemini,cerebras,openrouter"
    LLM_PRIMARY_MODEL: str = "groq/llama-3.3-70b-versatile"
    LLM_FALLBACK_MODELS: str = (
        "gemini/gemini-2.0-flash,"
        "cerebras/llama-3.3-70b,"
        "openrouter/meta-llama/llama-3.1-8b-instruct:free"
    )

    # ── Database ─────────────────────────────────────────────────────────────
    DATABASE_URL: str = ""

    # ── Cache ────────────────────────────────────────────────────────────────
    REDIS_URL: str = ""

    # ── Scraping ─────────────────────────────────────────────────────────────
    TAVILY_API_KEY: str = ""
    FIRECRAWL_API_KEY: str = ""
    BRIGHTDATA_API_KEY: str = ""
    BRIGHTDATA_ZONE: str = "unlocker"

    # ── Image Generation ─────────────────────────────────────────────────────
    IMAGE_GEN_API_KEY: str = ""
    IMAGE_GEN_PROVIDER: str = "fal"

    # ── WordPress ────────────────────────────────────────────────────────────
    WP_BASE_URL: str = "https://kakilambe.com"
    WP_USERNAME: str = "kora_publisher"
    WP_APP_PASSWORD: str = ""

    # ── Gmail ────────────────────────────────────────────────────────────────
    GMAIL_CLIENT_ID: str = ""
    GMAIL_CLIENT_SECRET: str = ""
    GMAIL_REFRESH_TOKEN: str = ""
    GMAIL_RECIPIENT: str = "mistermarcket@gmail.com"

    # ── Scheduling ───────────────────────────────────────────────────────────
    CYCLE_HOUR: int = 6
    CYCLE_TIMEZONE: str = "Africa/Conakry"

    # ── Security ─────────────────────────────────────────────────────────────
    API_SECRET_KEY: str = ""
    ADMIN_SECRET_KEY: str = ""
    ADMIN_EMAIL: str = "mistermarcket@gmail.com"

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = True
        extra = "ignore"  # Ignore les variables .env non déclarées dans Settings


settings = Settings()
