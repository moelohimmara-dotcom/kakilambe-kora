import httpx
import base64
from typing import Optional

from core.config import settings
from core.logger import logger


class WordPressClient:
    def __init__(self):
        self.base_url = settings.WP_BASE_URL.rstrip("/")
        self._auth = base64.b64encode(
            f"{settings.WP_USERNAME}:{settings.WP_APP_PASSWORD}".encode()
        ).decode()

    @property
    def _headers(self) -> dict:
        return {
            "Authorization": f"Basic {self._auth}",
            "Content-Type": "application/json",
        }

    async def test_connection(self) -> dict:
        async with httpx.AsyncClient(timeout=10) as client:
            r = await client.get(
                f"{self.base_url}/wp-json/wp/v2/users/me",
                headers=self._headers,
            )
            r.raise_for_status()
            data = r.json()
            return {"ok": True, "user": data.get("name"), "id": data.get("id")}

    async def publish_post(self, article: dict) -> str:
        payload = {
            "title": article.get("titre", ""),
            "content": article.get("corps", ""),
            "excerpt": article.get("chapeau", ""),
            "status": "publish",
            "meta": {
                "_yoast_wpseo_metadesc": article.get("meta_description", ""),
            },
        }
        if article.get("categorie_id"):
            payload["categories"] = [article["categorie_id"]]
        if article.get("wp_media_id"):
            payload["featured_media"] = article["wp_media_id"]

        async with httpx.AsyncClient(timeout=30) as client:
            r = await client.post(
                f"{self.base_url}/wp-json/wp/v2/posts",
                headers=self._headers,
                json=payload,
            )
            r.raise_for_status()
            data = r.json()
            logger.info("wp_post_created", post_id=data["id"], link=data["link"])
            return data["link"]

    async def upload_media(
        self,
        image_url: str,
        filename: str = "kora-image.jpg",
        alt_text: str = "",
    ) -> Optional[int]:
        async with httpx.AsyncClient(timeout=45, follow_redirects=True) as client:
            img_response = await client.get(image_url)
            img_response.raise_for_status()
            image_bytes = img_response.content

        headers = {
            "Authorization": f"Basic {self._auth}",
            "Content-Disposition": f'attachment; filename="{filename}"',
            "Content-Type": "image/jpeg",
        }
        async with httpx.AsyncClient(timeout=30) as client:
            r = await client.post(
                f"{self.base_url}/wp-json/wp/v2/media",
                headers=headers,
                content=image_bytes,
            )
            r.raise_for_status()
            media_id = r.json()["id"]

        # Nettoyer caption/description (WordPress lit l'EXIF pollinations.ai sinon)
        async with httpx.AsyncClient(timeout=15) as client:
            await client.post(
                f"{self.base_url}/wp-json/wp/v2/media/{media_id}",
                headers=self._headers,
                json={
                    "alt_text": alt_text or filename.replace("-", " ").replace(".jpg", ""),
                    "caption": "",
                    "description": "",
                },
            )

        return media_id


wp_client = WordPressClient()
