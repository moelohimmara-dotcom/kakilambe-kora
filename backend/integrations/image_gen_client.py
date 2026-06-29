import urllib.parse
from typing import Optional

import httpx

from core.logger import logger


class ImageGenClient:
    """Génération d'images via pollinations.ai (gratuit, sans clé API)."""

    async def generate(self, prompt: str) -> Optional[str]:
        return await self._pollinations_generate(prompt)

    async def _pollinations_generate(self, prompt: str) -> Optional[str]:
        try:
            encoded = urllib.parse.quote(prompt[:400])
            url = (
                f"https://image.pollinations.ai/prompt/{encoded}"
                "?width=1280&height=720&model=flux&nologo=true"
            )
            # Vérification que l'image est bien générée (HEAD ou GET partiel)
            async with httpx.AsyncClient(timeout=45, follow_redirects=True) as client:
                r = await client.get(url)
                r.raise_for_status()
            logger.info("pollinations_image_ok", size=len(r.content))
            return url
        except Exception as e:
            logger.error("pollinations_image_failed", error=str(e))
        return None


image_gen_client = ImageGenClient()
