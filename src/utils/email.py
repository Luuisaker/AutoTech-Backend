import logging
import resend

from src.config.settings import settings

logger = logging.getLogger(__name__)


def _init_resend() -> None:
    if settings.RESEND_API_KEY and not resend.api_key:
        resend.api_key = settings.RESEND_API_KEY


async def send_email(to: str, subject: str, body: str) -> None:
    if not settings.RESEND_API_KEY:
        logger.warning("RESEND_API_KEY not set, skipping email send")
        return
    _init_resend()
    try:
        logger.info(f"Attempting to send email to {to}: {subject}")
        resp = await resend.Emails.send_async({
            "from": settings.RESEND_FROM,
            "to": [to],
            "subject": subject,
            "html": body,
        })
        logger.info(f"Email sent to {to}: {subject} (id={resp.get('id') if isinstance(resp, dict) else resp})")
    except Exception as e:
        logger.error(f"Failed to send email to {to}: {subject} — Error: {e}", exc_info=True)
        raise
