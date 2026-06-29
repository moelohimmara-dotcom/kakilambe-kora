from typing import Optional
from core.config import settings
from core.logger import logger


class FirecrawlClient:
    def __init__(self):
        self.api_key = settings.FIRECRAWL_API_KEY

    async def scrape(self, url: str) -> Optional[str]:
        try:
            from firecrawl import FirecrawlApp
            app = FirecrawlApp(api_key=self.api_key)
            result = app.scrape_url(url, params={"formats": ["markdown"]})
            return result.get("markdown", "")
        except Exception as e:
            logger.error("firecrawl_scrape_failed", url=url, error=str(e))
            return None


firecrawl_client = FirecrawlClient()
