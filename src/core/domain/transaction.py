from typing import Any
from abc import ABC, abstractmethod


class GenericTransaction(ABC):
    def __init__(self, **kwargs) -> None:
        pass

    def __getattr__(self, name: str) -> Any:
        pass

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if exc_type is None:
            await self.commit()
        else:
            await self.rollback()

        await self.close()

    @abstractmethod
    async def commit(self):
        raise NotImplementedError

    @abstractmethod
    async def rollback(self):
        raise NotImplementedError

    @abstractmethod
    async def close(self):
        raise NotImplementedError
