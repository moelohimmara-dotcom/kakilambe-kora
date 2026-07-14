import asyncio
from typing import Optional
from core.config import settings
from core.logger import logger


class FirecrawlClient:
    def __init__(self):
        self.api_key = settings.FIRECRAWL_API_KEY

    def _scrape_sync(self, url: str) -> Optional[str]:
        from firecrawl import FirecrawlApp
        app = FirecrawlApp(api_key=self.api_key)
        result = app.scrape_url(url, params={"formats": ["markdown"]})
        return result.get("markdown", "")

    async def scrape(self, url: str) -> Optional[str]:
        # firecrawl-py 0.0.16 est un SDK SYNCHRONE (requests, pas httpx) — sans
        # to_thread(), cet appel bloquait TOUTE la boucle d'événements asyncio
        # (uvicorn --workers 1) pendant sa durée complète. Conséquences réelles
        # observées : le sémaphore de concurrence d'agent/nodes/scraper.py
        # (_ENRICH_CONCURRENCY=4) n'avait aucun effet — les appels s'exécutaient
        # en réalité en série, pas en parallèle — et asyncio.wait_for(timeout=15)
        # ne pouvait pas interrompre un appel bloquant déjà en cours, tout comme
        # les autres requêtes du serveur (health checks compris) restaient
        # gelées pendant ce temps. to_thread() délègue l'appel à un thread du
        # pool par défaut, rendant la boucle d'événements réellement libre.
        try:
            return await asyncio.to_thread(self._scrape_sync, url)
        except Exception as e:
            logger.error("firecrawl_scrape_failed", url=url, error=str(e))
            return None


firecrawl_client = FirecrawlClient()
