from typing import Optional, Generic, TypeVar
from pydantic import BaseModel

T = TypeVar("T", bound=BaseModel)


class Response(BaseModel, Generic[T]):
    success: bool
    status_code: int
    content: Optional[T] = None
    message: Optional[str] = None
    min_down_payment_percentage: Optional[float] = None
