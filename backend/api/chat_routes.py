import json
import asyncio
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy import text
from typing import Optional, List

from core.llm_router import llm_router
from core.logger import logger
from db.connection import get_db

router = APIRouter()

# Identité par défaut de l'assistant — alignée sur docs-reference/KORA_AGENT_SPEC.md.
# Utilisée si le frontend n'envoie pas de system_prompt explicite.
_DEFAULT_SYSTEM_PROMPT = (
    "Tu es KORA, l'agent éditorial autonome de GuinéePress Intelligence "
    "(kakilambe.com). Tu opères via un pipeline LangGraph (scraping Tavily/"
    "Firecrawl, sélection et agrégation éditoriale, rédaction, illustration "
    "fal.ai, publication WordPress) avec validation humaine (HITL) en mode "
    "semi-automatique. Ici, dans ce chat, tu assistes l'utilisateur — "
    "rédaction, recherche, brouillons d'articles — avec le même ton neutre, "
    "factuel et professionnel que les articles publiés. Réponds en français.\n\n"
    "TU DISPOSES DE L'OUTIL search_web_for_news. Utilise-le SYSTÉMATIQUEMENT "
    "pour toute question sur l'actualité, un événement récent, ou une "
    "information qui nécessite des données à jour (au-delà de ta date de "
    "connaissance). Ne dis jamais que tu n'as pas accès à des informations "
    "en temps réel sans avoir d'abord appelé cet outil. "
    "INTERDICTION ABSOLUE : ne prétends JAMAIS avoir utilisé un outil que tu "
    "n'as pas réellement invoqué. Si aucun résultat de recherche web ne t'a "
    "été fourni dans la conversation, réponds avec tes connaissances "
    "générales en précisant explicitement leur date de validité limitée — "
    "n'invente jamais de faits récents ni de citations d'un outil fictif."
)

# ── Outil de recherche web (Tavily) — le chat n'avait aucun accès temps réel ──
# Déclenchement déterministe (voir _is_news_query/_run_tool_loop), pas de
# function-calling LLM : les petits modèles du fallback chain (openrouter 8B)
# ne le supportent pas de façon fiable, et l'aller-retour de décision doublait
# la latence jusqu'au 504 Gateway Timeout sur DigitalOcean.


async def _execute_tool_call(name: str, arguments: dict) -> str:
    if name != "search_web_for_news":
        return "Outil inconnu."

    from integrations.tavily_client import tavily_client
    query = arguments.get("query") or "actualité Guinée Conakry"
    # search_depth="basic" + timeout court : le chat a besoin d'une réponse rapide
    # (contrainte gateway DigitalOcean ~60s), contrairement au pipeline éditorial
    # qui peut se permettre "advanced" en tâche de fond.
    results = await tavily_client.search(query, max_results=4, search_depth="basic", timeout=10)

    logger.info("chat_tool_call_executed", tool=name, query=query, results_count=len(results))

    if not results:
        return f"Aucun résultat trouvé pour la recherche « {query} »."

    formatted = "\n\n".join(
        f"- {r.get('title', 'Sans titre')} ({r.get('url', '')})\n  {(r.get('content') or '')[:300]}"
        for r in results
    )
    return f"Résultats de recherche web pour « {query} » :\n\n{formatted}"


# ── Détection déterministe des questions d'actualité ─────────────────────────
# Laisser le LLM "décider" (function-calling tool_choice="auto") s'est montré
# peu fiable : variance run-to-run, confabulation, et un aller-retour LLM en
# plus. Un simple filtre mots-clés déclenche la recherche de façon prévisible.
_NEWS_TRIGGER_KEYWORDS = (
    "actualite", "actualites", "nouvelles", "derniere", "dernieres",
    "recent", "recente", "recentes", "aujourd'hui", "aujourdhui",
    "cette semaine", "ce mois", "en ce moment", "news",
)
_ACCENT_MAP = str.maketrans("àâäéèêëîïôöùûüç", "aaaeeeeiioouuuc")


def _is_news_query(text_: str) -> bool:
    normalized = (text_ or "").lower().translate(_ACCENT_MAP)
    return any(kw in normalized for kw in _NEWS_TRIGGER_KEYWORDS)


async def _run_tool_loop(
    messages: list, temperature: float, max_tokens: int, force: bool = False, query_hint: str = ""
) -> tuple[list, bool]:
    """
    Retourne (messages_enrichis, tool_used).

    `force=True` (mot-clé d'actualité détecté) : appelle Tavily DIRECTEMENT en Python,
    sans solliciter le LLM pour "décider" — élimine un aller-retour LLM complet.
    Une passe de décision LLM séparée doublait la latence (2 complétions par tour) et
    provoquait des 504 Gateway Timeout sur DigitalOcean dès qu'un provider de repli
    (fallback) plus lent que groq était utilisé. Le déclenchement déterministe est
    aussi plus fiable que tool_choice="auto", qui montrait de la confabulation
    (le modèle prétendait avoir cherché sans appeler l'outil).

    `force=False` : pas de recherche — évite tout appel d'outil superflu pour les
    questions non liées à l'actualité (écriture, reformulation, etc.).
    """
    if not force:
        return messages, False

    try:
        result = await _execute_tool_call("search_web_for_news", {"query": query_hint})
        logger.info("chat_tool_call_triggered", query=query_hint)
        enriched = list(messages) + [
            {"role": "system", "content": f"[Résultat de recherche web injecté automatiquement]\n{result}"}
        ]
        return enriched, True
    except Exception as e:
        logger.warning("chat_tool_loop_failed", error=str(e))
        return messages, False


class ChatMessage(BaseModel):
    role: str
    content: str


class ChatRequest(BaseModel):
    messages: List[ChatMessage]
    session_id: Optional[str] = None
    system_prompt: Optional[str] = None
    temperature: float = 0.7
    max_tokens: int = 2048
    stream: bool = False
    debug: bool = False  # inclut tool_used/tool_forced dans la réponse — usage QA uniquement


class ImproveRequest(BaseModel):
    prompt: str
    context: Optional[str] = None


class SessionPatch(BaseModel):
    title: Optional[str] = None
    is_pinned: Optional[bool] = None
    status: Optional[str] = None


# ── Persistance sessions/messages ────────────────────────────────────────────
# Le chat n'écrivait rien en base avant cette route : chaque rechargement de
# page perdait l'historique. Ces helpers sont utilisés par POST "" et /stream.

async def _persist_message(session_id: str, role: str, content: str, title_candidate: Optional[str] = None):
    try:
        async with get_db() as db:
            await db.execute(
                text("INSERT INTO chat_messages (session_id, role, content) VALUES (:sid, :role, :content)"),
                {"sid": session_id, "role": role, "content": content},
            )
            await db.execute(
                text("""
                UPDATE chat_sessions
                SET message_count = message_count + 1,
                    updated_at = now(),
                    title = COALESCE(title, :title)
                WHERE id = :id
                """),
                {"title": (title_candidate or "")[:60] or None, "id": session_id},
            )
    except Exception as e:
        logger.warning("chat_persist_failed", session_id=session_id, error=str(e))


@router.post("")
async def chat(body: ChatRequest):
    messages = [{"role": "system", "content": body.system_prompt or _DEFAULT_SYSTEM_PROMPT}]
    messages.extend([m.dict() for m in body.messages])

    last_user_text = body.messages[-1].content if body.messages else ""
    messages, tool_used = await _run_tool_loop(
        messages, body.temperature, body.max_tokens,
        force=_is_news_query(last_user_text), query_hint=last_user_text,
    )

    try:
        # Résultats Tavily déjà injectés comme message système par _run_tool_loop —
        # un seul appel LLM ici, pas de binding tools/tool_choice nécessaire.
        response = await llm_router.complete(
            messages=messages,
            temperature=body.temperature,
            max_tokens=body.max_tokens,
        )
        content = response.choices[0].message.content
    except Exception as e:
        logger.error("chat_final_completion_failed", error=str(e), tool_used=tool_used)
        raise HTTPException(status_code=502, detail="Le modèle n'a pas pu générer de réponse. Réessayez.")

    if body.session_id and body.messages:
        last_user = body.messages[-1].content
        await _persist_message(body.session_id, "user", last_user, title_candidate=last_user)
        await _persist_message(body.session_id, "assistant", content)

    result = {"role": "assistant", "content": content}
    if body.debug:
        result["tool_used"] = tool_used
        result["tool_forced"] = _is_news_query(last_user_text)
    return result


@router.post("/sessions")
async def create_session():
    """Crée une session vide (titre défini au premier message)."""
    async with get_db() as db:
        result = await db.execute(
            text("INSERT INTO chat_sessions (title) VALUES (NULL) RETURNING id, title, is_pinned, status, message_count, created_at, updated_at")
        )
        row = result.mappings().first()
    return dict(row)


@router.get("/stream")
async def chat_stream(session_id: str, message: str, temperature: float = 0.7):
    """SSE streaming chat response. Persiste le message utilisateur et la réponse assemblée."""
    await _persist_message(session_id, "user", message, title_candidate=message)

    async def generate():
        messages = [
            {"role": "system", "content": _DEFAULT_SYSTEM_PROMPT},
            {"role": "user", "content": message},
        ]
        accumulated = ""
        try:
            # Phase 1 — recherche Tavily déterministe (Python, pas de décision LLM
            # séparée) si mot-clé d'actualité détecté. Un seul appel LLM streamé suit.
            messages, tool_used = await _run_tool_loop(
                messages, temperature, max_tokens=400, force=_is_news_query(message), query_hint=message
            )
            if tool_used:
                yield f"data: {json.dumps({'event': 'tool_call', 'tool': 'search_web_for_news'})}\n\n"

            response = await llm_router.complete(
                messages=messages,
                temperature=temperature,
                stream=True,
            )
            async for chunk in response:
                delta = chunk.choices[0].delta
                if delta and delta.content:
                    accumulated += delta.content
                    payload = json.dumps({"token": delta.content})
                    yield f"data: {payload}\n\n"
            if accumulated:
                await _persist_message(session_id, "assistant", accumulated)
            yield "data: [DONE]\n\n"
        except Exception as e:
            yield f"data: {json.dumps({'error': str(e)})}\n\n"

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.post("/improve")
async def improve_prompt(body: ImproveRequest):
    """Meta-prompting: improve the user's prompt."""
    system = (
        "Tu es un expert en prompt engineering. "
        "Améliore le prompt de l'utilisateur pour qu'il soit plus précis, "
        "contextuel et produise de meilleures réponses de KORA. "
        "Réponds uniquement avec le prompt amélioré, sans explication."
    )
    messages = [
        {"role": "system", "content": system},
        {"role": "user", "content": f"Améliore ce prompt:\n\n{body.prompt}"},
    ]
    response = await llm_router.complete(messages=messages, temperature=0.4)
    improved = response.choices[0].message.content
    return {"improved_prompt": improved, "original_prompt": body.prompt}


@router.post("/export")
async def export_to_article(body: ChatRequest):
    """Export a chat response to the article pipeline."""
    messages = [m.dict() for m in body.messages]
    response = await llm_router.complete(messages=messages, temperature=0.7)
    content = response.choices[0].message.content

    async with get_db() as db:
        result = await db.execute(
            text("""
            INSERT INTO articles (titre, corps, status, origin)
            VALUES (:titre, :corps, 'DRAFT', 'CHAT_EXPORT')
            RETURNING id
            """),
            {"titre": "Article depuis Chat KORA", "corps": content},
        )
        article_id = result.scalar()

    return {"article_id": str(article_id), "status": "DRAFT"}


@router.get("/sessions")
async def list_sessions():
    """Conversations actives, épinglées en premier puis les plus récentes."""
    async with get_db() as db:
        result = await db.execute(
            text("""
            SELECT id, title, is_pinned, status, created_at, updated_at, message_count
            FROM chat_sessions
            WHERE status != 'archived'
            ORDER BY is_pinned DESC, updated_at DESC
            LIMIT 50
            """)
        )
        rows = result.mappings().all()
    return [dict(r) for r in rows]


@router.get("/sessions/{session_id}")
async def get_session_messages(session_id: str):
    async with get_db() as db:
        session_result = await db.execute(
            text("SELECT id, title, is_pinned, status, created_at, updated_at, message_count FROM chat_sessions WHERE id = :id"),
            {"id": session_id},
        )
        session_row = session_result.mappings().first()
        if not session_row:
            raise HTTPException(status_code=404, detail="Session non trouvée")

        result = await db.execute(
            text("SELECT role, content, created_at FROM chat_messages WHERE session_id = :id ORDER BY created_at"),
            {"id": session_id},
        )
        messages = [dict(r) for r in result.mappings().all()]

    return {"session": dict(session_row), "messages": messages}


@router.patch("/sessions/{session_id}")
async def update_session(session_id: str, body: SessionPatch):
    fields = {k: v for k, v in body.dict().items() if v is not None}
    if not fields:
        raise HTTPException(status_code=400, detail="No fields to update")
    if "status" in fields and fields["status"] not in ("active", "archived"):
        raise HTTPException(status_code=400, detail="status must be 'active' or 'archived'")

    set_clause = ", ".join(f"{k} = :{k}" for k in fields)
    fields["id"] = session_id

    async with get_db() as db:
        result = await db.execute(
            text(f"UPDATE chat_sessions SET {set_clause}, updated_at = now() WHERE id = :id "
                 "RETURNING id, title, is_pinned, status, created_at, updated_at, message_count"),
            fields,
        )
        row = result.mappings().first()
    if not row:
        raise HTTPException(status_code=404, detail="Session non trouvée")
    return dict(row)


@router.delete("/sessions/{session_id}")
async def delete_session(session_id: str):
    async with get_db() as db:
        result = await db.execute(
            text("SELECT id FROM chat_sessions WHERE id = :id"), {"id": session_id}
        )
        if not result.mappings().first():
            raise HTTPException(status_code=404, detail="Session non trouvée")
        await db.execute(text("DELETE FROM chat_sessions WHERE id = :id"), {"id": session_id})
    return {"deleted": True}
