import httpx
import base64
import markdown
from typing import Optional

from core.config import settings
from core.logger import logger

# writer.py produit du Markdown (## sous-titres) — WordPress n'interprète pas
# ce format par défaut (the_content ne fait que wpautop, pas de rendu Markdown
# sans plugin dédié) : les "##" apparaissaient littéralement sur le site publié.
# Converti en HTML propre au moment de l'envoi ; le champ `corps` reste en
# Markdown en base, c'est le format source éditable, pas ce qui part vers WP.
def _corps_to_html(corps: str) -> str:
    return markdown.markdown(corps or "", extensions=["nl2br"])


class WordPressClient:
    def __init__(self):
        self._base_url_env = settings.WP_BASE_URL.rstrip("/")
        self._username_env = settings.WP_USERNAME
        self._password_env = settings.WP_APP_PASSWORD

    async def _get_credentials(self) -> tuple[str, str]:
        """
        Priorité : settings DB (modifiables depuis l'UI) → variables d'environnement.
        """
        try:
            from db.connection import get_db
            from sqlalchemy import text
            async with get_db() as db:
                result = await db.execute(
                    text("SELECT key, value FROM app_settings WHERE key IN ('wp_url','wp_username','wp_app_password')")
                )
                rows = {r["key"]: r["value"] for r in result.mappings().all()}
            base_url = (rows.get("wp_url") or self._base_url_env).rstrip("/")
            username = rows.get("wp_username") or self._username_env
            password = rows.get("wp_app_password") or self._password_env
            return base_url, base64.b64encode(f"{username}:{password}".encode()).decode()
        except Exception:
            base_url = self._base_url_env
            auth = base64.b64encode(f"{self._username_env}:{self._password_env}".encode()).decode()
            return base_url, auth

    async def _headers(self) -> dict:
        _, auth = await self._get_credentials()
        return {"Authorization": f"Basic {auth}", "Content-Type": "application/json"}

    async def test_connection(self) -> dict:
        base_url, auth = await self._get_credentials()
        headers = {"Authorization": f"Basic {auth}", "Content-Type": "application/json"}
        async with httpx.AsyncClient(timeout=10) as client:
            r = await client.get(f"{base_url}/wp-json/wp/v2/users/me", headers=headers)
            r.raise_for_status()
            data = r.json()
            return {"ok": True, "user": data.get("name"), "id": data.get("id")}

    async def list_categories(self) -> list[dict]:
        """Catégories réelles définies sur le site WordPress (id, name, slug)."""
        base_url, auth = await self._get_credentials()
        headers = {"Authorization": f"Basic {auth}", "Content-Type": "application/json"}
        categories: list[dict] = []
        page = 1
        async with httpx.AsyncClient(timeout=15) as client:
            while True:
                r = await client.get(
                    f"{base_url}/wp-json/wp/v2/categories",
                    headers=headers,
                    params={"per_page": 100, "page": page},
                )
                if r.status_code == 400:  # page au-delà du total — fin de pagination WP
                    break
                r.raise_for_status()
                batch = r.json()
                if not batch:
                    break
                categories.extend({"wp_id": c["id"], "name": c["name"], "slug": c["slug"]} for c in batch)
                if len(batch) < 100:
                    break
                page += 1
        return categories

    async def publish_post(self, article: dict) -> str:
        base_url, auth = await self._get_credentials()
        headers = {"Authorization": f"Basic {auth}", "Content-Type": "application/json"}

        payload = {
            "title":   article.get("titre", ""),
            "content": _corps_to_html(article.get("corps", "")),
            "excerpt": article.get("chapeau", ""),
            "status":  "publish",
            "meta": {"_yoast_wpseo_metadesc": article.get("meta_description", "")},
        }
        if article.get("categorie_id"):
            payload["categories"] = [article["categorie_id"]]
        if article.get("wp_media_id"):
            payload["featured_media"] = article["wp_media_id"]

        async with httpx.AsyncClient(timeout=30) as client:
            r = await client.post(f"{base_url}/wp-json/wp/v2/posts", headers=headers, json=payload)
            r.raise_for_status()
            data = r.json()
            logger.info("wp_post_created", post_id=data["id"], link=data["link"])
            return data["link"]

    async def upload_media(
        self,
        image_url: str,
        filename: str = "kora-image.jpg",
        alt_text: str = "",
    ) -> tuple[int, Optional[str]]:
        base_url, auth = await self._get_credentials()

        async with httpx.AsyncClient(timeout=45, follow_redirects=True) as client:
            img_response = await client.get(image_url)
            img_response.raise_for_status()
            image_bytes = img_response.content

        upload_headers = {
            "Authorization": f"Basic {auth}",
            "Content-Disposition": f'attachment; filename="{filename}"',
            "Content-Type": "image/jpeg",
        }
        async with httpx.AsyncClient(timeout=30) as client:
            r = await client.post(
                f"{base_url}/wp-json/wp/v2/media",
                headers=upload_headers,
                content=image_bytes,
            )
            r.raise_for_status()
            media_id = r.json()["id"]

        # Nettoyer alt/caption et récupérer l'URL hébergée sur WordPress
        json_headers = {"Authorization": f"Basic {auth}", "Content-Type": "application/json"}
        wp_image_url = None
        async with httpx.AsyncClient(timeout=15) as client:
            patch = await client.post(
                f"{base_url}/wp-json/wp/v2/media/{media_id}",
                headers=json_headers,
                json={
                    "alt_text":    alt_text or filename.replace("-", " ").replace(".jpg", ""),
                    "caption":     "",
                    "description": "",
                },
            )
            if patch.status_code < 400:
                wp_image_url = patch.json().get("source_url", "")

        return media_id, wp_image_url


wp_client = WordPressClient()
