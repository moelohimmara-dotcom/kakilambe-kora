from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from core.llm_router import llm_router, PROVIDER_CONFIG, PROVIDER_ORDER

router = APIRouter()


class OverrideRequest(BaseModel):
    status: str  # ACTIVE | RATE_LIMITED | EXHAUSTED | OFFLINE


@router.get("")
async def get_providers():
    """Return current state of all LLM providers."""
    states = llm_router.get_all_provider_states()
    result = []
    for name in PROVIDER_ORDER:
        state = states[name]
        cfg = PROVIDER_CONFIG[name]
        limit = cfg.get("daily_token_limit")
        used = state.get("tokens_used_today", 0)
        result.append({
            "name": name,
            "model": cfg["primary_model"],
            "status": state.get("status", "ACTIVE"),
            "tokens_used_today": used,
            "daily_token_limit": limit,
            "usage_pct": round(used / limit * 100, 1) if limit else None,
            "requests_today": state.get("requests_today", 0),
            "rate_limited_until": state.get("rate_limited_until"),
        })
    return result


@router.post("/{provider}/override")
async def override_provider(provider: str, body: OverrideRequest):
    allowed = {"ACTIVE", "RATE_LIMITED", "EXHAUSTED", "OFFLINE"}
    if body.status not in allowed:
        raise HTTPException(status_code=400, detail=f"Invalid status. Allowed: {allowed}")
    try:
        llm_router.override_provider_status(provider, body.status)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    state = llm_router.get_provider_state(provider)
    await llm_router.persist_to_db(provider, state)
    return {"provider": provider, "status": body.status, "updated": True}


@router.post("/reset")
async def reset_providers():
    """Reset all provider states to ACTIVE."""
    llm_router.reset_all_providers()
    await llm_router.persist_all_to_db()
    return {"reset": True, "providers": PROVIDER_ORDER}
