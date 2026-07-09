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
