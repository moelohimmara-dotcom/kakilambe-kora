"""
KoraLLMRouter — fallback chain groq → gemini → cerebras → openrouter
State persistence : in-memory (sync) + Supabase provider_states (async)
Pas de Redis requis.
"""
import litellm
import json
from datetime import datetime, timedelta
from typing import Optional

from core.config import settings
from core.logger import logger

litellm.set_verbose = False

PROVIDER_CONFIG = {
    "groq": {
        "primary_model": "groq/llama-3.3-70b-versatile",
        "fallback_model": "groq/llama-3.1-8b-instant",
        "daily_token_limit": 500_000,
        "rpm_limit": 30,
        "api_key_env": "GROQ_API_KEY",
    },
    "gemini": {
        "primary_model": "gemini/gemini-2.0-flash",
        "daily_token_limit": 1_000_000,
        "rpm_limit": 15,
        "api_key_env": "GEMINI_API_KEY",
    },
    "cerebras": {
        "primary_model": "cerebras/llama3.3-70b",
        "daily_token_limit": 200_000,
        "rpm_limit": 30,
        "api_key_env": "CEREBRAS_API_KEY",
    },
    "openrouter": {
        "primary_model": "openrouter/meta-llama/llama-3.1-8b-instruct",
        "daily_token_limit": None,
        "rpm_limit": 20,
        "api_key_env": "OPENROUTER_API_KEY",
    },
}

FALLBACK_CHAIN = [
    PROVIDER_CONFIG["groq"]["primary_model"],
    PROVIDER_CONFIG["gemini"]["primary_model"],
    PROVIDER_CONFIG["cerebras"]["primary_model"],
    PROVIDER_CONFIG["openrouter"]["primary_model"],
]

PROVIDER_ORDER = ["groq", "gemini", "cerebras", "openrouter"]


class KoraLLMRouter:
    def __init__(self):
        # Cache mémoire — source de vérité pendant l'exécution
        self._cache: dict[str, dict] = {}

    # ── State defaults ───────────────────────────────────────────────────────

    def _default_state(self) -> dict:
        return {
            "status": "ACTIVE",
            "tokens_used_today": 0,
            "requests_today": 0,
            "rate_limited_until": None,
            "exhausted_until": None,
        }

    # ── Sync in-memory access (utilisé pendant les cycles) ───────────────────

    def get_provider_state(self, provider: str) -> dict:
        return dict(self._cache.get(provider, self._default_state()))

    def set_provider_state(self, provider: str, state: dict):
        self._cache[provider] = dict(state)

    def get_all_provider_states(self) -> dict:
        return {p: self.get_provider_state(p) for p in PROVIDER_ORDER}

    def override_provider_status(self, provider: str, status: str):
        if provider not in PROVIDER_CONFIG:
            raise ValueError(f"Unknown provider: {provider}")
        state = self.get_provider_state(provider)
        state["status"] = status
        self.set_provider_state(provider, state)

    def reset_all_providers(self):
        for provider in PROVIDER_ORDER:
            self.set_provider_state(provider, self._default_state())

    # ── Supabase persistence ─────────────────────────────────────────────────

    async def load_from_db(self):
        """Charge les états depuis Supabase au démarrage de l'app."""
        try:
            from db.connection import get_db
            from sqlalchemy import text
            async with get_db() as db:
                result = await db.execute(text(
                    "SELECT provider, status, tokens_used_today, requests_today, "
                    "last_error, rate_limited_until, exhausted_until "
                    "FROM provider_states"
                ))
                rows = result.mappings().all()
            for row in rows:
                self._cache[row["provider"]] = {
                    "status": row["status"] or "ACTIVE",
                    "tokens_used_today": row["tokens_used_today"] or 0,
                    "requests_today": row["requests_today"] or 0,
                    "rate_limited_until": (
                        row["rate_limited_until"].isoformat()
                        if row["rate_limited_until"] else None
                    ),
                    "exhausted_until": (
                        row["exhausted_until"].isoformat()
                        if row["exhausted_until"] else None
                    ),
                    "last_error": row["last_error"],
                }
            logger.info("provider_states_loaded", count=len(rows))
        except Exception as e:
            logger.warning("provider_states_load_failed", error=str(e))

    async def persist_to_db(self, provider: str, state: dict):
        """Persiste un état provider dans Supabase (upsert)."""
        try:
            from db.connection import get_db
            from sqlalchemy import text
            from datetime import datetime as _dt

            def _parse_ts(val):
                """Convertit une string ISO en datetime (asyncpg attend un objet datetime)."""
                if val is None:
                    return None
                if isinstance(val, _dt):
                    return val
                try:
                    return _dt.fromisoformat(val)
                except (ValueError, TypeError):
                    return None

            async with get_db() as db:
                await db.execute(text("""
                    INSERT INTO provider_states
                        (provider, status, tokens_used_today, requests_today,
                         last_error, rate_limited_until, exhausted_until, updated_at)
                    VALUES
                        (:provider, :status, :tokens, :requests,
                         :last_error, :rate_limited_until, :exhausted_until, now())
                    ON CONFLICT (provider) DO UPDATE SET
                        status              = EXCLUDED.status,
                        tokens_used_today   = EXCLUDED.tokens_used_today,
                        requests_today      = EXCLUDED.requests_today,
                        last_error          = EXCLUDED.last_error,
                        rate_limited_until  = EXCLUDED.rate_limited_until,
                        exhausted_until     = EXCLUDED.exhausted_until,
                        updated_at          = now()
                """), {
                    "provider":            provider,
                    "status":              state.get("status", "ACTIVE"),
                    "tokens":              state.get("tokens_used_today", 0),
                    "requests":            state.get("requests_today", 0),
                    "last_error":          state.get("last_error"),
                    "rate_limited_until":  _parse_ts(state.get("rate_limited_until")),
                    "exhausted_until":     _parse_ts(state.get("exhausted_until")),
                })
        except Exception as e:
            logger.warning("provider_state_persist_failed", provider=provider, error=str(e))

    async def persist_all_to_db(self):
        """Persiste tous les états en base (utilisé par reset)."""
        for provider, state in self._cache.items():
            await self.persist_to_db(provider, state)

    # ── Active provider selection ────────────────────────────────────────────

    def get_active_provider(self) -> Optional[str]:
        for provider in PROVIDER_ORDER:
            state = self.get_provider_state(provider)
            status = state.get("status", "ACTIVE")

            if status == "ACTIVE":
                limit = PROVIDER_CONFIG[provider]["daily_token_limit"]
                if limit and state.get("tokens_used_today", 0) >= limit:
                    state["status"] = "EXHAUSTED"
                    self.set_provider_state(provider, state)
                    continue
                return provider

            elif status in ("RATE_LIMITED", "OFFLINE"):
                limited_until = state.get("rate_limited_until")
                if limited_until and datetime.utcnow().isoformat() > limited_until:
                    state["status"] = "ACTIVE"
                    state["rate_limited_until"] = None
                    self.set_provider_state(provider, state)
                    return provider

        return None

    # ── LLM completion with automatic fallback ───────────────────────────────

    async def complete(
        self,
        messages: list,
        temperature: float = 0.7,
        max_tokens: int = 2048,
        stream: bool = False,
        response_format=None,
        tools: Optional[list] = None,
        tool_choice=None,
    ):
        active = self.get_active_provider()
        if not active:
            raise RuntimeError("All LLM providers exhausted or offline")

        primary_model = PROVIDER_CONFIG[active]["primary_model"]
        fallbacks = [m for m in FALLBACK_CHAIN if m != primary_model]

        params = {
            "model": primary_model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": stream,
            "fallbacks": fallbacks,
            "num_retries": 2,
        }
        if response_format:
            params["response_format"] = response_format
        if tools:
            params["tools"] = tools
            params["tool_choice"] = tool_choice or "auto"

        self._set_litellm_keys()

        try:
            response = await litellm.acompletion(**params)

            state = self.get_provider_state(active)
            if hasattr(response, "usage") and response.usage:
                state["tokens_used_today"] += response.usage.total_tokens
                state["requests_today"] += 1
            self.set_provider_state(active, state)
            await self.persist_to_db(active, state)

            logger.info(
                "llm_success",
                provider=active,
                model=primary_model,
                tokens=getattr(getattr(response, "usage", None), "total_tokens", 0),
            )
            return response

        except litellm.RateLimitError:
            state = self.get_provider_state(active)
            state["status"] = "RATE_LIMITED"
            state["rate_limited_until"] = (
                datetime.utcnow() + timedelta(seconds=60)
            ).isoformat()
            self.set_provider_state(active, state)
            await self.persist_to_db(active, state)
            logger.warning("rate_limited", provider=active)
            raise

        except litellm.ContextWindowExceededError:
            logger.warning("context_exceeded", provider=active)
            raise

        except litellm.NotFoundError as e:
            # 404 modèle invalide → EXHAUSTED (permanent, pas de retry)
            state = self.get_provider_state(active)
            state["status"] = "EXHAUSTED"
            state["last_error"] = str(e)[:200]
            self.set_provider_state(active, state)
            await self.persist_to_db(active, state)
            logger.error("llm_model_not_found", provider=active, error=str(e)[:200])
            raise

        except Exception as e:
            state = self.get_provider_state(active)
            state["status"] = "OFFLINE"
            state["rate_limited_until"] = (
                datetime.utcnow() + timedelta(minutes=5)
            ).isoformat()
            state["last_error"] = str(e)[:200]
            self.set_provider_state(active, state)
            await self.persist_to_db(active, state)
            logger.error("llm_error", provider=active, error=str(e)[:200])
            raise

    def _set_litellm_keys(self):
        if settings.GROQ_API_KEY:
            litellm.groq_key = settings.GROQ_API_KEY
        if settings.GEMINI_API_KEY:
            litellm.gemini_key = settings.GEMINI_API_KEY
        if settings.CEREBRAS_API_KEY:
            litellm.cerebras_key = settings.CEREBRAS_API_KEY
        if settings.OPENROUTER_API_KEY:
            litellm.openrouter_key = settings.OPENROUTER_API_KEY


# Singleton
llm_router = KoraLLMRouter()
