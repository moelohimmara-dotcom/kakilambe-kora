from typing import List, Optional
from core.config import settings
from core.logger import logger


class TavilyClient:
    def __init__(self):
        self.api_key = settings.TAVILY_API_KEY

    async def search(self, query: str, max_results: int = 10) -> List[dict]:
        try:
            from tavily import TavilyClient as _Tavily
            client = _Tavily(api_key=self.api_key)
            result = client.search(query, max_results=max_results, search_depth="advanced")
            return result.get("results", [])
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
