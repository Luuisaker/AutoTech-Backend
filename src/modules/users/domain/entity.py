from dataclasses import dataclass
from src.core.domain.entity import Entity


@dataclass
class User(Entity):
    email: str
    password_hash: str
    roles: list[str]
    first_name: str
    last_name: str
    ci: str
    phone: str
    photo_url: str | None = None
    is_suspended: int = 0
    client_average_rating: float = 0.0
    client_rating_count: int = 0
    credit_level: int = 1
    parts_credit_limit: float = 150.0
    service_credit_limit: float = 50.0
    credit_points: float = 0.0
    total_parts_debt: float = 0.0
    total_service_debt: float = 0.0
    is_2fa_enabled: int = 0
    language_preference: str = "es"
