"""BCV rate fetching utilities for historical rates."""

import logging
from datetime import datetime, date, timedelta
from typing import Optional
import httpx

from src.config.settings import settings

logger = logging.getLogger(__name__)


class BcvRateInfo:
    def __init__(self, usd: float, eur: float, date: str | datetime):
        self.usd = usd
        self.eur = eur
        if isinstance(date, str):
            self.date = datetime.fromisoformat(date)
        else:
            self.date = date


async def _fetch_dolarapi(target_date: date) -> Optional[BcvRateInfo]:
    """Fetch BCV rate from dolarapi.com (most reliable)."""
    url = f"https://ve.dolarapi.com/v1/dolares/bcv"
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get(url)
            if response.status_code == 200:
                data = response.json()
                usd = data.get("promedio") or data.get("usd") or data.get("rate")
                if usd and usd > 0:
                    api_date = data.get("fechaActualizacion") or data.get("date")
                    return BcvRateInfo(usd=float(usd), eur=0, date=api_date or target_date.isoformat())
    except Exception as e:
        logger.warning("dolarapi.com falló: %s", e)
    return None


async def _fetch_dolarvzla(target_date: date) -> Optional[BcvRateInfo]:
    """Fetch BCV rate from rates.dolarvzla.com (historical)."""
    url = f"https://rates.dolarvzla.com/bcv/{target_date.year}/{target_date.month}/{target_date.day}.json"
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get(url)
            if response.status_code == 200:
                data = response.json()
                usd = data.get("usd")
                eur = data.get("eur", 0)
                api_date = data.get("date")
                if usd and usd > 0:
                    return BcvRateInfo(usd=float(usd), eur=float(eur), date=api_date or target_date.isoformat())
    except Exception as e:
        logger.warning("rates.dolarvzla.com falló: %s", e)
    return None


async def _fetch_configurable(target_date: date) -> Optional[BcvRateInfo]:
    """Fetch BCV rate from the configurable BCV_API_URL."""
    url = settings.BCV_API_URL
    if not url:
        return None
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get(url)
            if response.status_code == 200:
                data = response.json()
                usd = data.get("promedio") or data.get("usd") or data.get("rate")
                if usd and usd > 0:
                    api_date = data.get("fechaActualizacion") or data.get("date")
                    return BcvRateInfo(usd=float(usd), eur=0, date=api_date or target_date.isoformat())
    except Exception as e:
        logger.warning("BCV_API_URL %s falló: %s", url, e)
    return None


async def fetch_bcv_rate_for_date(target_date: date) -> Optional[BcvRateInfo]:
    """
    Fetch BCV rate for a specific date using multiple sources as fallback.
    Order: configurable URL -> dolarapi.com -> rates.dolarvzla.com
    Returns None if all sources fail.
    """
    sources = [
        ("configurable", _fetch_configurable(target_date)),
        ("dolarapi", _fetch_dolarapi(target_date)),
        ("dolarvzla", _fetch_dolarvzla(target_date)),
    ]

    for name, coro in sources:
        try:
            rate = await coro
            if rate:
                logger.info("BCV rate obtenido de %s: $%.2f", name, rate.usd)
                return rate
        except Exception as e:
            logger.warning("Fuente BCV '%s' falló: %s", name, e)

    logger.error("Todas las fuentes BCV fallaron para %s", target_date)
    return None


async def get_bcv_rate_for_date(dt: datetime) -> Optional[BcvRateInfo]:
    """
    Get BCV rate for a datetime (uses date portion).
    Falls back to previous business day if weekend/holiday.
    """
    current_date = dt.date()

    rate = await fetch_bcv_rate_for_date(current_date)
    if rate:
        return rate

    for i in range(1, 6):
        fallback_date = current_date - timedelta(days=i)
        if fallback_date.weekday() >= 5:
            continue
        rate = await fetch_bcv_rate_for_date(fallback_date)
        if rate:
            return rate

    return None
