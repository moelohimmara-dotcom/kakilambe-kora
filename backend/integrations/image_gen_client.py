import urllib.parse
from typing import Optional

import httpx

from core.config import settings
from core.logger import logger


class ImageGenClient:
    """Génération d'images via pollinations.ai (gratuit, sans clé API)."""

    async def generate(self, prompt: str) -> Optional[str]:
        return await self._pollinations_generate(prompt)

    async def _pollinations_generate(self, prompt: str) -> Optional[str]:
        # Nettoyer le prompt : ASCII uniquement, espaces normalisés
        safe_prompt = prompt[:400].encode("ascii", "ignore").decode("ascii").strip()
        if not safe_prompt:
            safe_prompt = "Guinea Africa news illustration"

        encoded = urllib.parse.quote(safe_prompt)
        url = (
            f"https://image.pollinations.ai/prompt/{encoded}"
            "?width=1280&height=720&model=flux&nologo=true&nofeed=true"
        )
        # Token en paramètre d'URL (pas en header) : wordpress_client.py
        # retélécharge cette même URL telle quelle pour l'upload WordPress —
        # un header ne survivrait pas à ce second appel.
        if settings.POLLINATIONS_API_KEY:
            url += f"&token={settings.POLLINATIONS_API_KEY}"

        for attempt in range(3):
            try:
                async with httpx.AsyncClient(timeout=60, follow_redirects=True) as client:
                    r = await client.get(url)
                    r.raise_for_status()
                    # Vérifier que c'est bien une image (pas du JSON)
                    ct = r.headers.get("content-type", "")
                    if "image" not in ct:
                        logger.warning("pollinations_not_image", content_type=ct, attempt=attempt)
                        continue
                logger.info("pollinations_image_ok", size=len(r.content), attempt=attempt)
                return url
            except Exception as e:
                logger.warning("pollinations_retry", attempt=attempt, error=str(e))

        logger.error("pollinations_image_failed", prompt=safe_prompt[:80])
        return None


image_gen_client = ImageGenClient()
