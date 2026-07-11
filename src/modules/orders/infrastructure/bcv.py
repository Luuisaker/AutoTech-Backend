"""BCV rate fetching utilities for historical rates."""

from datetime import datetime, date, timedelta
from typing import Optional
import httpx


class BcvRateInfo:
    def __init__(self, usd: float, eur: float, date: str):
        self.usd = usd
        self.eur = eur
        self.date = date


async def fetch_bcv_rate_for_date(target_date: date) -> Optional[BcvRateInfo]:
    """
    Fetch BCV rate for a specific date from CDN.
    Returns None if not found (weekend/holiday) or on error.
    """
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
                    return BcvRateInfo(usd=usd, eur=eur, date=api_date or target_date.isoformat())
            elif response.status_code == 404:
                return None
    except Exception:
        return None
    
    return None


async def get_bcv_rate_for_date(dt: datetime) -> Optional[BcvRateInfo]:
    """
    Get BCV rate for a datetime (uses date portion).
    Falls back to previous business day if weekend/holiday.
    """
    current_date = dt.date()
    
    # Try current date first
    rate = await fetch_bcv_rate_for_date(current_date)
    if rate:
        return rate
    
    # Fallback: go back to previous business day (max 5 days)
    for i in range(1, 6):
        fallback_date = current_date - timedelta(days=i)
        # Skip weekends
        if fallback_date.weekday() >= 5:  # 5=Saturday, 6=Sunday
            continue
        rate = await fetch_bcv_rate_for_date(fallback_date)
        if rate:
            return rate
    
    return None