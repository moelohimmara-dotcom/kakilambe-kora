from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from sqlalchemy import text
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
        result = await db.execute(text("SELECT key, value FROM app_settings"))
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
                text(
                    "INSERT INTO app_settings (key, value) VALUES (:k, :v) "
                    "ON CONFLICT (key) DO UPDATE SET value = :v, updated_at = now()"
                ),
                {"k": key, "v": str(value)},
            )
    return {"updated": list(updates.keys())}


# ── Prompts ──────────────────────────────────────────────────────────────────

@router.get("/prompts")
async def list_prompts():
    async with get_db() as db:
        result = await db.execute(
            text("SELECT id, name, content, is_default, is_builtin, temperature FROM system_prompts")
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
            text(
                "INSERT INTO system_prompts (name, content, temperature, is_default) "
                "VALUES (:name, :content, :temp, :default) RETURNING id"
            ),
            {"name": body.name, "content": body.content,
             "temp": body.temperature, "default": body.is_default},
        )
        prompt_id = result.scalar()
    return {"id": str(prompt_id), "created": True}


@router.patch("/prompts/{prompt_id}")
async def update_prompt(prompt_id: str, body: PromptCreate):
    async with get_db() as db:
        await db.execute(
            text(
                "UPDATE system_prompts SET name=:name, content=:content, "
                "temperature=:temp, is_default=:default WHERE id=:id"
            ),
            {"name": body.name, "content": body.content,
             "temp": body.temperature, "default": body.is_default, "id": prompt_id},
        )
    return {"updated": True}


# ── Sources RSS ───────────────────────────────────────────────────────────────

@router.get("/sources")
async def list_sources():
    async with get_db() as db:
        result = await db.execute(
            text("SELECT id, name, url, category, is_active, last_synced, error_count FROM rss_sources ORDER BY name")
        )
        rows = result.mappings().all()
    return [dict(r) for r in rows]


@router.post("/sources")
async def create_source(body: SourceCreate):
    async with get_db() as db:
        result = await db.execute(
            text("INSERT INTO rss_sources (name, url, category) VALUES (:name, :url, :cat) RETURNING id"),
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
        await db.execute(text(f"UPDATE rss_sources SET {set_clause} WHERE id = :id"), fields)
    return {"updated": True}


@router.delete("/sources/{source_id}")
async def delete_source(source_id: str):
    async with get_db() as db:
        await db.execute(text("DELETE FROM rss_sources WHERE id = :id"), {"id": source_id})
    return {"deleted": True}


# ── Test email ────────────────────────────────────────────────────────────────

@router.post("/test-email")
async def test_email():
    from integrations.gmail_client import gmail_client
    from datetime import datetime
    import pytz
    from core.config import settings

    resend_key = getattr(settings, "RESEND_API_KEY", "")
    smtp_user = getattr(settings, "GMAIL_USER", "")
    smtp_pw = getattr(settings, "GMAIL_APP_PASSWORD", "")
    if not resend_key and not (smtp_user and smtp_pw):
        raise HTTPException(status_code=503, detail="Aucune configuration email trouvée (RESEND_API_KEY ou GMAIL_USER+GMAIL_APP_PASSWORD requis)")

    last_error: list[str] = []
    original_send = gmail_client._send_via_resend if resend_key else gmail_client._send_via_smtp

    async def patched_resend(api_key, subject, body_html, recipient):
        from core.logger import logger as _log
        import httpx as _httpx
        sender = getattr(settings, "RESEND_FROM", "KORA GuinéePress <onboarding@resend.dev>")
        try:
            async with _httpx.AsyncClient(timeout=15) as client:
                resp = await client.post(
                    "https://api.resend.com/emails",
                    headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
                    json={"from": sender, "to": [recipient], "subject": subject, "html": body_html},
                )
                resp.raise_for_status()
            _log.info("email_sent", provider="resend", to=recipient, subject=subject)
        except Exception as e:
            last_error.append(str(e))
            raise

    now = datetime.now(pytz.timezone(settings.CYCLE_TIMEZONE)).strftime("%d/%m/%Y %H:%M")
    body = f"""
    <div style="font-family:sans-serif;max-width:500px;margin:auto;padding:24px">
      <div style="font-size:22px;font-weight:700;margin-bottom:12px">
        <span style="color:#f97316">/</span>KORA — Test email ✅
      </div>
      <p>Les notifications email sont correctement configurées.</p>
      <p style="color:#6b7280;font-size:13px">Envoyé le {now} (Conakry)</p>
    </div>
    """
    try:
        await gmail_client.send_report(subject=f"[KORA] Test de notification — {now}", body_html=body)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Échec envoi email : {e}")

    if last_error:
        raise HTTPException(status_code=500, detail=f"Échec envoi email : {last_error[0]}")

    return {"sent": True, "to": settings.GMAIL_RECIPIENT, "provider": "resend" if resend_key else "smtp"}


# ── Catégories WordPress (item 8 — synchronisation dynamique) ────────────────
# Remplace les IDs codés en dur dans writer.py par un mapping réel, synchronisé
# depuis l'API WordPress, éditable par l'utilisateur dans /settings.

_KORA_LABELS = ["Politique", "Économie", "Société", "Sport", "Culture", "Sécurité", "International"]
_ACCENT_MAP = str.maketrans("àâäéèêëîïôöùûüç", "aaaeeeeiioouuuc")


def _norm(s: str) -> str:
    return (s or "").strip().lower().translate(_ACCENT_MAP)


class CategoryMappingPatch(BaseModel):
    kora_label: Optional[str] = None  # None = retire le mapping


@router.post("/wp-categories/sync")
async def sync_wp_categories():
    """
    Récupère les vraies catégories du site WordPress et les synchronise en
    base. Auto-associe un libellé KORA si le nom correspond exactement
    (insensible à la casse/accents) ; ne touche jamais un mapping déjà
    défini manuellement par l'utilisateur.
    """
    from integrations.wordpress_client import wp_client
    try:
        categories = await wp_client.list_categories()
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Échec de synchronisation WordPress : {e}")

    label_by_norm = {_norm(label): label for label in _KORA_LABELS}

    synced = 0
    async with get_db() as db:
        for cat in categories:
            existing = await db.execute(
                text("SELECT kora_label FROM wp_categories WHERE wp_id = :wp_id"),
                {"wp_id": cat["wp_id"]},
            )
            row = existing.mappings().first()
            auto_label = None if row else label_by_norm.get(_norm(cat["name"]))

            await db.execute(
                text("""
                    INSERT INTO wp_categories (wp_id, name, slug, kora_label, synced_at)
                    VALUES (:wp_id, :name, :slug, :auto_label, now())
                    ON CONFLICT (wp_id) DO UPDATE SET
                        name = EXCLUDED.name,
                        slug = EXCLUDED.slug,
                        synced_at = now()
                """),
                {"wp_id": cat["wp_id"], "name": cat["name"], "slug": cat["slug"], "auto_label": auto_label},
            )
            synced += 1

    return {"synced": synced, "categories": categories}


@router.get("/wp-categories")
async def list_wp_categories():
    async with get_db() as db:
        result = await db.execute(
            text("SELECT wp_id, name, slug, kora_label, synced_at FROM wp_categories ORDER BY name")
        )
        rows = result.mappings().all()
    return [dict(r) for r in rows]


@router.patch("/wp-categories/{wp_id}")
async def update_wp_category_mapping(wp_id: int, body: CategoryMappingPatch):
    if body.kora_label is not None and body.kora_label not in _KORA_LABELS:
        raise HTTPException(status_code=400, detail=f"kora_label doit être l'un de {_KORA_LABELS}")

    async with get_db() as db:
        result = await db.execute(
            text("UPDATE wp_categories SET kora_label = :label WHERE wp_id = :wp_id RETURNING wp_id"),
            {"label": body.kora_label, "wp_id": wp_id},
        )
        if not result.first():
            raise HTTPException(status_code=404, detail="Catégorie non trouvée — synchronisez d'abord")
    return {"wp_id": wp_id, "kora_label": body.kora_label}
