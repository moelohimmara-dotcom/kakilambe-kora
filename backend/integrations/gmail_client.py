"""
Email client via Resend API (https://resend.com).
Variable requise : RESEND_API_KEY (commence par re_)
Fallback : GMAIL_USER + GMAIL_APP_PASSWORD via SMTP si Resend non configuré.
"""
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Optional

import httpx

from core.config import settings
from core.logger import logger


class GmailClient:
    async def send_report(self, subject: str, body_html: str, to: Optional[str] = None):
        recipient = to or getattr(settings, "GMAIL_RECIPIENT", "")
        if not recipient:
            logger.info("email_skipped", reason="no recipient configured")
            return

        resend_key = getattr(settings, "RESEND_API_KEY", "")
        if resend_key:
            await self._send_via_resend(resend_key, subject, body_html, recipient)
            return

        # Fallback SMTP
        user = getattr(settings, "GMAIL_USER", "")
        app_pw = getattr(settings, "GMAIL_APP_PASSWORD", "")
        if user and app_pw:
            await self._send_via_smtp(user, app_pw, subject, body_html, recipient)
            return

        logger.info("email_skipped", reason="no email credentials configured")

    async def _send_via_resend(self, api_key: str, subject: str, body_html: str, recipient: str):
        sender = getattr(settings, "RESEND_FROM", "KORA GuinéePress <onboarding@resend.dev>")
        try:
            async with httpx.AsyncClient(timeout=15) as client:
                resp = await client.post(
                    "https://api.resend.com/emails",
                    headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
                    json={"from": sender, "to": [recipient], "subject": subject, "html": body_html},
                )
                resp.raise_for_status()
            logger.info("email_sent", provider="resend", to=recipient, subject=subject)
        except Exception as e:
            logger.error("email_send_failed", provider="resend", error=str(e))

    async def _send_via_smtp(self, user: str, app_pw: str, subject: str, body_html: str, recipient: str):
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = f"KORA · GuinéePress <{user}>"
        msg["To"] = recipient
        msg.attach(MIMEText(body_html, "html", "utf-8"))
        try:
            with smtplib.SMTP("smtp.gmail.com", 587, timeout=15) as smtp:
                smtp.ehlo()
                smtp.starttls()
                smtp.ehlo()
                smtp.login(user, app_pw)
                smtp.sendmail(user, recipient, msg.as_bytes())
            logger.info("email_sent", provider="smtp", to=recipient, subject=subject)
        except Exception as e:
            logger.error("email_send_failed", provider="smtp", error=str(e))


gmail_client = GmailClient()
