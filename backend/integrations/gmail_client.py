"""
Gmail client via SMTP + App Password (pas d'OAuth2 requis).
Variables requises : GMAIL_USER, GMAIL_APP_PASSWORD, GMAIL_RECIPIENT
"""
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Optional

from core.config import settings
from core.logger import logger


class GmailClient:
    async def send_report(self, subject: str, body_html: str, to: Optional[str] = None):
        user = getattr(settings, "GMAIL_USER", "")
        app_pw = getattr(settings, "GMAIL_APP_PASSWORD", "")
        recipient = to or getattr(settings, "GMAIL_RECIPIENT", "")

        if not user or not app_pw:
            logger.info("gmail_skipped", reason="credentials not configured")
            return
        if not recipient:
            logger.info("gmail_skipped", reason="no recipient configured")
            return

        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = f"KORA · GuinéePress <{user}>"
        msg["To"] = recipient
        msg.attach(MIMEText(body_html, "html", "utf-8"))

        try:
            with smtplib.SMTP_SSL("smtp.gmail.com", 465, timeout=15) as smtp:
                smtp.login(user, app_pw)
                smtp.sendmail(user, recipient, msg.as_bytes())
            logger.info("gmail_sent", to=recipient, subject=subject)
        except Exception as e:
            logger.error("gmail_send_failed", error=str(e))


gmail_client = GmailClient()
