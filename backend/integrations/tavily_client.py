from typing import List, Optional
import httpx
from core.config import settings
from core.logger import logger

_TAVILY_API_URL = "https://api.tavily.com/search"


class TavilyClient:
    def __init__(self):
        self.api_key = settings.TAVILY_API_KEY

    async def search(
        self,
        query: str,
        max_results: int = 10,
        search_depth: str = "advanced",
        timeout: float = 20,
        topic: Optional[str] = None,
        days: Optional[int] = None,
    ) -> List[dict]:
        """
        Appel direct à l'API Tavily via httpx — évite la dépendance cohere du SDK.

        topic="news" + days=1 : active le filtre de fraîcheur natif de Tavily
        (résultats des dernières 24h uniquement) et fait apparaître le champ
        `published_date` sur chaque résultat, exploité ensuite pour un second
        filtre défensif côté scraper (cf. agent/nodes/scraper.py).
        """
        if not self.api_key:
            logger.error("tavily_no_api_key")
            return []
        try:
            payload = {
                "api_key": self.api_key,
                "query": query,
                "max_results": max_results,
                "search_depth": search_depth,
                "include_raw_content": False,
            }
            if topic:
                payload["topic"] = topic
            if days is not None:
                payload["days"] = days
            async with httpx.AsyncClient(timeout=timeout) as client:
                r = await client.post(_TAVILY_API_URL, json=payload)
                r.raise_for_status()
                return r.json().get("results", [])
        except Exception as e:
            logger.error("tavily_search_failed", query=query, error=str(e))
            return []

    async def search_guinea_news(self, max_results: int = 20) -> List[dict]:
        queries = [
            "actualité Guinée Conakry",
            "Guinea Conakry news today",
            "Afrique de l'Ouest actualités",
        ]
        all_results = []
        for q in queries:
            results = await self.search(q, max_results=max_results // len(queries))
            all_results.extend(results)
        # Deduplicate by URL
        seen = set()
        unique = []
        for r in all_results:
            if r.get("url") not in seen:
                seen.add(r.get("url"))
                unique.append(r)
        return unique


tavily_client = TavilyClient()
