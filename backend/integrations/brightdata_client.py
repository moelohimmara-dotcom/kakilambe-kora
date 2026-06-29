import httpx
from typing import Optional
from core.config import settings
from core.logger import logger


class BrightDataClient:
    """Fallback scraper using BrightData Unlocker."""

    async def fetch(self, url: str) -> Optional[str]:
        try:
            proxy = f"http://{settings.BRIGHTDATA_API_KEY}@brd.superproxy.io:22225"
            async with httpx.AsyncClient(proxies={"http://": proxy, "https://": proxy}, timeout=20) as client:
                r = await client.get(url)
                r.raise_for_status()
                return r.text
        except Exception as e:
            logger.error("brightdata_fetch_failed", url=url, error=str(e))
            return None


brightdata_client = BrightDataClient()
