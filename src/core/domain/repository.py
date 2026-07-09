from abc import ABC, abstractmethod
from typing import Generic, TypeVar, Sequence

T = TypeVar("T")


class GenericRepository(Generic[T], ABC):
    @abstractmethod
    async def get(self, id_: str) -> T | None:
        raise NotImplementedError

    @abstractmethod
    async def list(self, offset: int = 0, limit: int = 100, **filters) -> Sequence[T]:
        raise NotImplementedError

    @abstractmethod
    async def add(self, record: T) -> T:
        raise NotImplementedError

    @abstractmethod
    async def update(self, record: T) -> T:
        raise NotImplementedError

    @abstractmethod
    async def delete(self, record: T) -> None:
        raise NotImplementedError
