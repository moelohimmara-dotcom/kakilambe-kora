from typing import Optional
from core.config import settings
from core.logger import logger


class ImageGenClient:
    async def generate(self, prompt: str) -> Optional[str]:
        provider = settings.IMAGE_GEN_PROVIDER.lower()
        if provider == "fal":
            return await self._fal_generate(prompt)
        logger.warning("unknown_image_provider", provider=provider)
        return None

    async def _fal_generate(self, prompt: str) -> Optional[str]:
        try:
            import fal_client

            def on_queue_update(update):
                pass

            result = fal_client.subscribe(
                "fal-ai/flux/schnell",
                arguments={"prompt": prompt, "image_size": "landscape_16_9", "num_images": 1},
                with_logs=False,
                on_queue_update=on_queue_update,
            )
            images = result.get("images", [])
            if images:
                return images[0].get("url")
        except Exception as e:
            logger.error("fal_image_failed", error=str(e))
        return None


image_gen_client = ImageGenClient()
