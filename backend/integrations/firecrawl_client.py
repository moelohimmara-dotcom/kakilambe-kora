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
        # onlyMainContent=True — sans ce paramètre explicite, le markdown
        # renvoyé inclut la navigation/le header/les articles suggérés du
        # site source, qui peuvent occuper l'intégralité des 3000 premiers
        # caractères pris par _build_sources_section() (agent/nodes/writer.py)
        # et évincer entièrement le vrai corps de l'article. Root cause
        # découverte le 2026-07-14 en traçant pourquoi les articles restaient
        # trop courts malgré un budget de tokens suffisant : le modèle
        # recevait presque exclusivement du menu de site, pas des faits — il
        # refusait (à raison) d'halluciner le reste pour atteindre 800 mots.
        result = app.scrape_url(url, params={"formats": ["markdown"], "onlyMainContent": True})
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
