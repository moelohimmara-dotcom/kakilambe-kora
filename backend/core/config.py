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
    # Gemini abandonné (décision explicite du propriétaire) — retiré de la
    # chaîne de fallback et du routeur (core/llm_router.py).
    GROQ_API_KEY: str = ""
    CEREBRAS_API_KEY: str = ""
    OPENROUTER_API_KEY: str = ""

    LLM_PROVIDER_ORDER: str = "groq,cerebras,openrouter"
    LLM_PRIMARY_MODEL: str = "groq/llama-3.3-70b-versatile"
    LLM_FALLBACK_MODELS: str = (
        "cerebras/llama-3.3-70b,"
        "openrouter/meta-llama/llama-3.1-8b-instruct:free"
    )

    # ── Database ─────────────────────────────────────────────────────────────
    DATABASE_URL: str = ""

    # ── Cache ────────────────────────────────────────────────────────────────
    REDIS_URL: str = ""

    # ── Scraping ─────────────────────────────────────────────────────────────
    # BrightData abandonné (identifiants proxy invalides en production,
    # décision explicite) — Firecrawl seul, repli sur l'extrait Tavily brut
    # en cas d'échec (cf. agent/nodes/scraper.py).
    TAVILY_API_KEY: str = ""
    FIRECRAWL_API_KEY: str = ""

    # ── Génération d'image ───────────────────────────────────────────────────
    # pollinations.ai fonctionne sans clé, mais un token relève les limites de
    # débit et garantit le rendu sans logo (nologo=true) de façon fiable.
    POLLINATIONS_API_KEY: str = ""

    # ── WordPress ────────────────────────────────────────────────────────────
    WP_BASE_URL: str = "https://kakilambe.com"
    WP_USERNAME: str = "kora_publisher"
    WP_APP_PASSWORD: str = ""

    # ── Email (Resend preferred, SMTP fallback) ───────────────────────────────
    RESEND_API_KEY: str = ""
    RESEND_FROM: str = "KORA GuinéePress <onboarding@resend.dev>"
    GMAIL_CLIENT_ID: str = ""
    GMAIL_CLIENT_SECRET: str = ""
    GMAIL_REFRESH_TOKEN: str = ""
    GMAIL_RECIPIENT: str = "mistermarcket@gmail.com"

    # ── Scheduling ───────────────────────────────────────────────────────────
    CYCLE_HOUR: int = 6
    CYCLE_TIMEZONE: str = "Africa/Conakry"

    # ── QStash (file d'attente Upstash pour publications différées/retries) ───
    QSTASH_TOKEN: str = ""
    QSTASH_CURRENT_SIGNING_KEY: str = ""
    QSTASH_NEXT_SIGNING_KEY: str = ""
    # Endpoint régional (ex. EU : https://qstash-eu-central-1.upstash.io) —
    # le SDK n'utilise l'endpoint générique que si celui-ci n'est pas fourni.
    QSTASH_URL: str = "https://qstash.upstash.io"
    # URL publique du backend — nécessaire pour que QStash sache où renvoyer
    # le webhook (il ne peut pas appeler localhost).
    APP_BASE_URL: str = "http://213.156.135.139"

    # ── Security ─────────────────────────────────────────────────────────────
    API_SECRET_KEY: str = ""
    ADMIN_SECRET_KEY: str = ""
    ADMIN_EMAIL: str = "mistermarcket@gmail.com"
    # Clé de signature des jetons de session (HS256) — distincte du mot de
    # passe utilisateur depuis la migration vers une vraie table `users`
    # (cf. core/security.py). Repli sur ADMIN_SECRET_KEY si non définie,
    # pour ne pas invalider tous les déploiements existants.
    SESSION_JWT_SECRET: str = ""
    GMAIL_USER: str = ""
    GMAIL_APP_PASSWORD: str = ""

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = True
        extra = "ignore"  # Ignore les variables .env non déclarées dans Settings


settings = Settings()
