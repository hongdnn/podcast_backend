"""
SMTP email service for scheduled podcast delivery notifications.
"""

import asyncio
import logging
import smtplib
import ssl
from email.message import EmailMessage

from app.core.config import settings

logger = logging.getLogger(__name__)


class EmailService:
    def __init__(self):
        self.smtp_host = settings.smtp_host
        self.smtp_port = settings.smtp_port
        self.smtp_username = settings.smtp_username
        self.smtp_password = settings.smtp_password
        self.smtp_use_tls = settings.smtp_use_tls
        self.smtp_use_ssl = settings.smtp_use_ssl
        self.email_from_address = settings.email_from_address or settings.smtp_username
        self.email_from_name = settings.email_from_name

    def is_configured(self) -> bool:
        return bool(
            self.smtp_host
            and self.smtp_port
            and self.email_from_address
            and self.smtp_username
            and self.smtp_password
        )

    async def send_scheduled_podcast_email(
        self,
        recipient_email: str,
        recipient_name: str,
        podcast_title: str,
        podcast_topic: str,
        audio_url: str,
    ) -> bool:
        """Send a scheduled podcast delivery email."""
        if not self.is_configured():
            logger.warning(
                "Scheduled podcast email skipped because SMTP settings are incomplete"
            )
            return False

        message = EmailMessage()
        message["Subject"] = f"Your {podcast_title} is ready"
        message["From"] = f"{self.email_from_name} <{self.email_from_address}>"
        message["To"] = recipient_email
        message.set_content(
            "\n".join(
                [
                    f"Hi {recipient_name},",
                    "",
                    f"Your scheduled {podcast_topic} podcast is ready.",
                    "",
                    f"Listen now: {audio_url}",
                    "",
                    "Thanks for using Podcastify.",
                ]
            )
        )

        try:
            await asyncio.to_thread(self._send_message, message)
            logger.info("Scheduled podcast email sent to %s", recipient_email)
            return True
        except Exception as e:
            logger.error(
                "Failed to send scheduled podcast email to %s: %s",
                recipient_email,
                str(e),
            )
            return False

    def _send_message(self, message: EmailMessage) -> None:
        context = ssl.create_default_context()

        if self.smtp_use_ssl:
            with smtplib.SMTP_SSL(
                self.smtp_host, self.smtp_port, context=context, timeout=30
            ) as server:
                server.login(self.smtp_username, self.smtp_password)
                server.send_message(message)
            return

        with smtplib.SMTP(self.smtp_host, self.smtp_port, timeout=30) as server:
            if self.smtp_use_tls:
                server.starttls(context=context)
            server.login(self.smtp_username, self.smtp_password)
            server.send_message(message)
