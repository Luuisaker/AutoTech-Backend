from pydantic import BaseModel


class PaginatedDTO(BaseModel):
    items: list
    total: int
    offset: int
    limit: int
