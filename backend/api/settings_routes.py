from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional

from db.connection import get_db

router = APIRouter()


class SettingsPatch(BaseModel):
    cycle_hour: Optional[int] = None
    cycle_timezone: Optional[str] = None
    articles_per_cycle: Optional[int] = None
    semi_auto_mode: Optional[bool] = None
    delay_between_posts: Optional[int] = None
    daily_report: Optional[bool] = None
    error_alerts: Optional[bool] = None


class SourceCreate(BaseModel):
    name: str
    url: str
    category: Optional[str] = None


class SourcePatch(BaseModel):
    name: Optional[str] = None
    is_active: Optional[bool] = None
    category: Optional[str] = None


@router.get("")
async def get_settings():
    async with get_db() as db:
        result = await db.execute("SELECT key, value FROM app_settings")
        rows = result.mappings().all()
    return {r["key"]: r["value"] for r in rows}


@router.patch("")
async def update_settings(body: SettingsPatch):
    updates = {k: v for k, v in body.dict().items() if v is not None}
    if not updates:
        raise HTTPException(status_code=400, detail="No fields to update")
    async with get_db() as db:
        for key, value in updates.items():
            await db.execute(
                "INSERT INTO app_settings (key, value) VALUES (:k, :v) "
                "ON CONFLICT (key) DO UPDATE SET value = :v, updated_at = now()",
                {"k": key, "v": str(value)},
            )
    return {"updated": list(updates.keys())}


# ── Prompts ──────────────────────────────────────────────────────────────────

@router.get("/prompts")
async def list_prompts():
    async with get_db() as db:
        result = await db.execute(
            "SELECT id, name, content, is_default, is_builtin, temperature FROM system_prompts"
        )
        rows = result.mappings().all()
    return [dict(r) for r in rows]


class PromptCreate(BaseModel):
    name: str
    content: str
    temperature: float = 0.7
    is_default: bool = False


@router.post("/prompts")
async def create_prompt(body: PromptCreate):
    async with get_db() as db:
        result = await db.execute(
            "INSERT INTO system_prompts (name, content, temperature, is_default) "
            "VALUES (:name, :content, :temp, :default) RETURNING id",
            {"name": body.name, "content": body.content,
             "temp": body.temperature, "default": body.is_default},
        )
        prompt_id = result.scalar()
    return {"id": str(prompt_id), "created": True}


@router.patch("/prompts/{prompt_id}")
async def update_prompt(prompt_id: str, body: PromptCreate):
    async with get_db() as db:
        await db.execute(
            "UPDATE system_prompts SET name=:name, content=:content, "
            "temperature=:temp, is_default=:default WHERE id=:id",
            {"name": body.name, "content": body.content,
             "temp": body.temperature, "default": body.is_default, "id": prompt_id},
        )
    return {"updated": True}


# ── Sources RSS ───────────────────────────────────────────────────────────────

@router.get("/sources")
async def list_sources():
    async with get_db() as db:
        result = await db.execute(
            "SELECT id, name, url, category, is_active, last_synced, error_count FROM rss_sources ORDER BY name"
        )
        rows = result.mappings().all()
    return [dict(r) for r in rows]


@router.post("/sources")
async def create_source(body: SourceCreate):
    async with get_db() as db:
        result = await db.execute(
            "INSERT INTO rss_sources (name, url, category) VALUES (:name, :url, :cat) RETURNING id",
            {"name": body.name, "url": body.url, "cat": body.category},
        )
        source_id = result.scalar()
    return {"id": str(source_id), "created": True}


@router.patch("/sources/{source_id}")
async def update_source(source_id: str, body: SourcePatch):
    fields = {k: v for k, v in body.dict().items() if v is not None}
    if not fields:
        raise HTTPException(status_code=400, detail="No fields to update")
    set_clause = ", ".join(f"{k} = :{k}" for k in fields)
    fields["id"] = source_id
    async with get_db() as db:
        await db.execute(f"UPDATE rss_sources SET {set_clause} WHERE id = :id", fields)
    return {"updated": True}


@router.delete("/sources/{source_id}")
async def delete_source(source_id: str):
    async with get_db() as db:
        await db.execute("DELETE FROM rss_sources WHERE id = :id", {"id": source_id})
    return {"deleted": True}
