"""
Client Upstash QStash — publication différée + vérification de signature webhook.

Utilise le SDK officiel `qstash` (pas de réimplémentation maison de la
vérification JWT/HMAC des signatures — trop sensible pour être hand-rolled,
contrairement aux appels REST simples type Tavily).
"""
from typing import Optional

from core.config import settings
from core.logger import logger


class QStashClient:
    def __init__(self):
        self._client = None
        self._receiver = None

    def _get_client(self):
        if self._client is None:
            from qstash import QStash
            self._client = QStash(settings.QSTASH_TOKEN, base_url=settings.QSTASH_URL)
        return self._client

    def _get_receiver(self):
        if self._receiver is None:
            from qstash import Receiver
            self._receiver = Receiver(
                current_signing_key=settings.QSTASH_CURRENT_SIGNING_KEY,
                next_signing_key=settings.QSTASH_NEXT_SIGNING_KEY,
            )
        return self._receiver

    @property
    def configured(self) -> bool:
        return bool(settings.QSTASH_TOKEN)

    async def publish_delayed(self, path: str, body: dict, delay_seconds: int = 0) -> Optional[str]:
        """
        Enfile un message QStash qui appellera POST {APP_BASE_URL}{path} après
        `delay_seconds`. Retourne le message_id QStash, ou None si non configuré
        ou en échec (l'appelant doit prévoir un repli — publication directe).
        """
        if not self.configured:
            logger.warning("qstash_not_configured")
            return None

        url = f"{settings.APP_BASE_URL.rstrip('/')}{path}"
        try:
            client = self._get_client()
            kwargs = {"url": url, "body": body}
            if delay_seconds > 0:
                kwargs["delay"] = f"{delay_seconds}s"
            result = client.message.publish_json(**kwargs)
            message_id = result.get("messageId") if isinstance(result, dict) else getattr(result, "message_id", None)
            logger.info("qstash_message_published", url=url, delay_seconds=delay_seconds, message_id=message_id)
            return message_id
        except Exception as e:
            logger.error("qstash_publish_failed", url=url, error=str(e))
            return None

    def verify_signature(self, body: str, signature: str, url: str) -> bool:
        """Vérifie la signature Upstash-Signature d'un webhook entrant."""
        if not settings.QSTASH_CURRENT_SIGNING_KEY:
            logger.warning("qstash_verify_no_signing_key")
            return False
        try:
            receiver = self._get_receiver()
            receiver.verify(body=body, signature=signature, url=url)
            return True
        except Exception as e:
            logger.warning("qstash_signature_invalid", error=str(e))
            return False


qstash_client = QStashClient()
