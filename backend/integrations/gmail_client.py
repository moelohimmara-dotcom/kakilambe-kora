import base64
from email.mime.text import MIMEText
from typing import Optional

from core.config import settings
from core.logger import logger


class GmailClient:
    def _get_service(self):
        from google.oauth2.credentials import Credentials
        from googleapiclient.discovery import build

        creds = Credentials(
            token=None,
            refresh_token=settings.GMAIL_REFRESH_TOKEN,
            client_id=settings.GMAIL_CLIENT_ID,
            client_secret=settings.GMAIL_CLIENT_SECRET,
            token_uri="https://oauth2.googleapis.com/token",
        )
        return build("gmail", "v1", credentials=creds)

    async def send_report(self, subject: str, body_html: str, to: Optional[str] = None):
        if not settings.GMAIL_REFRESH_TOKEN or not settings.GMAIL_CLIENT_ID:
            logger.info("gmail_skipped", reason="credentials not configured")
            return
        recipient = to or settings.GMAIL_RECIPIENT
        msg = MIMEText(body_html, "html")
        msg["to"] = recipient
        msg["subject"] = subject
        raw = base64.urlsafe_b64encode(msg.as_bytes()).decode()

        try:
            service = self._get_service()
            service.users().messages().send(userId="me", body={"raw": raw}).execute()
            logger.info("gmail_sent", to=recipient, subject=subject)
        except Exception as e:
            logger.error("gmail_send_failed", error=str(e))


gmail_client = GmailClient()
