import json
import asyncio
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import Optional, List

from core.llm_router import llm_router
from core.logger import logger
from db.connection import get_db

router = APIRouter()


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


class ImproveRequest(BaseModel):
    prompt: str
    context: Optional[str] = None


@router.post("")
async def chat(body: ChatRequest):
    messages = []
    if body.system_prompt:
        messages.append({"role": "system", "content": body.system_prompt})
    messages.extend([m.dict() for m in body.messages])

    response = await llm_router.complete(
        messages=messages,
        temperature=body.temperature,
        max_tokens=body.max_tokens,
    )
    content = response.choices[0].message.content
    return {"role": "assistant", "content": content}


@router.get("/stream")
async def chat_stream(session_id: str, message: str, temperature: float = 0.7):
    """SSE streaming chat response."""
    async def generate():
        messages = [{"role": "user", "content": message}]
        try:
            response = await llm_router.complete(
                messages=messages,
                temperature=temperature,
                stream=True,
            )
            async for chunk in response:
                delta = chunk.choices[0].delta
                if delta and delta.content:
                    payload = json.dumps({"token": delta.content})
                    yield f"data: {payload}\n\n"
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
            """
            INSERT INTO articles (titre, corps, status, origin)
            VALUES (:titre, :corps, 'DRAFT', 'CHAT_EXPORT')
            RETURNING id
            """,
            {"titre": "Article depuis Chat KORA", "corps": content},
        )
        article_id = result.scalar()

    return {"article_id": str(article_id), "status": "DRAFT"}


@router.get("/sessions")
async def list_sessions():
    async with get_db() as db:
        result = await db.execute(
            "SELECT id, title, created_at, message_count FROM chat_sessions ORDER BY created_at DESC LIMIT 50"
        )
        rows = result.mappings().all()
    return [dict(r) for r in rows]


@router.get("/sessions/{session_id}")
async def get_session_messages(session_id: str):
    async with get_db() as db:
        result = await db.execute(
            "SELECT role, content, created_at FROM chat_messages WHERE session_id = :id ORDER BY created_at",
            {"id": session_id},
        )
        rows = result.mappings().all()
    return [dict(r) for r in rows]
