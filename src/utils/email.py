import asyncio
import smtplib
from email.mime.text import MIMEText

from src.config.settings import settings


async def send_email(to: str, subject: str, body: str) -> None:
    if not settings.SMTP_HOST:
        return
    msg = MIMEText(body, "html")
    msg["Subject"] = subject
    msg["From"] = settings.SMTP_FROM_EMAIL
    msg["To"] = to
    loop = asyncio.get_event_loop()
    await loop.run_in_executor(None, _send_sync, msg)


def _send_sync(msg: MIMEText) -> None:
    with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT) as server:
        server.starttls()
        server.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
        server.send_message(msg)
