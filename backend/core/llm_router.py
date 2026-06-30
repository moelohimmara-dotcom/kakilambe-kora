import litellm
import redis
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
        "primary_model": "cerebras/llama-3.3-70b",
        "daily_token_limit": 200_000,
        "rpm_limit": 30,
        "api_key_env": "CEREBRAS_API_KEY",
    },
    "openrouter": {
        "primary_model": "openrouter/meta-llama/llama-3.1-8b-instruct:free",
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
        self._redis: Optional[redis.Redis] = None

    @property
    def redis(self) -> Optional[redis.Redis]:
        if self._redis is None and settings.REDIS_URL:
            try:
                self._redis = redis.from_url(settings.REDIS_URL, decode_responses=True)
            except Exception:
                pass
        return self._redis

    # ── Provider state ──────────────────────────────────────────────────────

    def get_provider_state(self, provider: str) -> dict:
        try:
            if self.redis is None:
                return {}
            data = self.redis.get(f"provider:{provider}")
            if data:
                return json.loads(data)
        except Exception:
            pass
        return {
            "status": "ACTIVE",
            "tokens_used_today": 0,
            "requests_today": 0,
            "rate_limited_until": None,
            "exhausted_until": None,
        }

    def set_provider_state(self, provider: str, state: dict):
        if self.redis is None:
            return
        try:
            self.redis.setex(f"provider:{provider}", 86400, json.dumps(state))
        except Exception as e:
            logger.error("redis_write_failed", provider=provider, error=str(e))

    def get_all_provider_states(self) -> dict:
        return {p: self.get_provider_state(p) for p in PROVIDER_ORDER}

    def reset_all_providers(self):
        for provider in PROVIDER_ORDER:
            self.set_provider_state(provider, {
                "status": "ACTIVE",
                "tokens_used_today": 0,
                "requests_today": 0,
                "rate_limited_until": None,
                "exhausted_until": None,
            })

    def override_provider_status(self, provider: str, status: str):
        if provider not in PROVIDER_CONFIG:
            raise ValueError(f"Unknown provider: {provider}")
        state = self.get_provider_state(provider)
        state["status"] = status
        self.set_provider_state(provider, state)

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

            elif status == "RATE_LIMITED":
                limited_until = state.get("rate_limited_until")
                if limited_until and datetime.utcnow().isoformat() > limited_until:
                    state["status"] = "ACTIVE"
                    self.set_provider_state(provider, state)
                    return provider

            elif status == "OFFLINE":
                # retry after 5 minutes
                limited_until = state.get("rate_limited_until")
                if limited_until and datetime.utcnow().isoformat() > limited_until:
                    state["status"] = "ACTIVE"
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

        # Inject API keys via env-aware approach
        self._set_litellm_keys()

        try:
            response = await litellm.acompletion(**params)

            state = self.get_provider_state(active)
            if hasattr(response, "usage") and response.usage:
                state["tokens_used_today"] += response.usage.total_tokens
                state["requests_today"] += 1
            self.set_provider_state(active, state)

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
            logger.warning("rate_limited", provider=active)
            raise

        except litellm.ContextWindowExceededError:
            logger.warning("context_exceeded", provider=active)
            raise

        except Exception as e:
            state = self.get_provider_state(active)
            state["status"] = "OFFLINE"
            state["rate_limited_until"] = (
                datetime.utcnow() + timedelta(minutes=5)
            ).isoformat()
            state["last_error"] = str(e)
            self.set_provider_state(active, state)
            logger.error("llm_error", provider=active, error=str(e))
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
