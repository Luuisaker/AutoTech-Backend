from dataclasses import dataclass
from uuid import UUID


@dataclass
class Entity:
    id: UUID

    created_at: str
    updated_at: str
